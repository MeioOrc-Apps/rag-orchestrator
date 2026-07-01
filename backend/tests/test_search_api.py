"""Tests for POST /search API — mocked OpenSearchClient and LLMClient."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration


def _os_hit(chunk_id: str, score: float = 1.0) -> dict:
    """Processed hit as returned by OpenSearchClient.search()."""
    return {
        "chunk_id": chunk_id,
        "file_id": "file-1",
        "domain": "docs",
        "chunk_index": 0,
        "source_language": "en",
        "content_en": "Some content",
        "content_pt": "Algum conteúdo",
        "highlight": "",
        "score": score,
    }


def _os_response(hits: list, total: int = None) -> dict:
    """Processed response as returned by OpenSearchClient.search()."""
    return {
        "total": total if total is not None else len(hits),
        "hits": hits,
    }


class TestSearchBasic:
    def test_search_returns_200(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.search.return_value = _os_response([])
            resp = api_client.post("/api/search", json={"query": "test"})
        assert resp.status_code == 200

    def test_search_response_has_required_fields(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.search.return_value = _os_response([_os_hit("abc")])
            resp = api_client.post("/api/search", json={"query": "test"})
        body = resp.json()
        assert "results" in body
        assert "total" in body
        assert "fallback_used" in body

    def test_search_calls_opensearch_with_query(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.search.return_value = _os_response([])
            api_client.post("/api/search", json={"query": "machine learning", "enrich": False})
        instance.search.assert_called_once()
        call_kwargs = instance.search.call_args
        assert "machine learning" in str(call_kwargs)

    def test_search_filters_by_domain(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.search.return_value = _os_response([])
            api_client.post("/api/search", json={"query": "test", "domain": "research", "enrich": False})
        call_kwargs = instance.search.call_args
        assert "research" in str(call_kwargs)

    def test_search_inserts_query_log(self, api_client, db_session):
        from app.models import SearchQueryLog
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.search.return_value = _os_response([])
            api_client.post("/api/search", json={"query": "hello", "enrich": False})
        # Need fresh session to see committed log
        from app.database import get_engine, get_session_factory
        import os
        engine = get_engine(os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://orchestrator:orchestrator@localhost:5433/orchestrator"))
        factory = get_session_factory(engine)
        s = factory()
        count = s.query(SearchQueryLog).count()
        s.close()
        engine.dispose()
        assert count >= 1


def _set_enrichment_model(db_session, model: str = "local:test-model") -> None:
    """Set enrichment_model in translation_settings so enrichment tests work."""
    from app.models import TranslationSettings
    ts = db_session.query(TranslationSettings).first()
    if ts:
        ts.enrichment_model = model
        db_session.commit()


class TestSearchEnrichment:
    def test_enrich_true_calls_llm_client(self, api_client, db_session):
        _set_enrichment_model(db_session)
        with patch("app.routers.search.OpenSearchClient") as MockOS, \
             patch("app.routers.search.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "enriched query"
            MockOS.return_value.search.return_value = _os_response([_os_hit("1")])
            resp = api_client.post("/api/search", json={"query": "test", "enrich": True})
        MockLLM.return_value.translate.assert_called_once()

    def test_enrich_false_skips_llm(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS, \
             patch("app.routers.search.LLMClient") as MockLLM:
            MockOS.return_value.search.return_value = _os_response([])
            api_client.post("/api/search", json={"query": "test", "enrich": False})
        MockLLM.return_value.translate.assert_not_called()

    def test_enrich_true_without_model_skips_llm(self, api_client):
        # enrichment_model is "" by default in test DB — LLM must not be called
        with patch("app.routers.search.OpenSearchClient") as MockOS, \
             patch("app.routers.search.LLMClient") as MockLLM:
            MockOS.return_value.search.return_value = _os_response([_os_hit("1")])
            api_client.post("/api/search", json={"query": "test", "enrich": True})
        MockLLM.return_value.translate.assert_not_called()

    def test_zero_results_with_enrich_retries_without(self, api_client, db_session):
        _set_enrichment_model(db_session)
        with patch("app.routers.search.OpenSearchClient") as MockOS, \
             patch("app.routers.search.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "enriched"
            # First call (enriched) → 0; second (original) → 1 hit
            MockOS.return_value.search.side_effect = [
                _os_response([], total=0),
                _os_response([_os_hit("1")], total=1),
            ]
            resp = api_client.post("/api/search", json={"query": "test", "enrich": True})
        body = resp.json()
        assert body["fallback_used"] is True
        assert body["total"] == 1

    def test_zero_results_without_enrich_no_retry(self, api_client):
        with patch("app.routers.search.OpenSearchClient") as MockOS:
            MockOS.return_value.search.return_value = _os_response([], total=0)
            resp = api_client.post("/api/search", json={"query": "test", "enrich": False})
        body = resp.json()
        assert body["fallback_used"] is False
        assert MockOS.return_value.search.call_count == 1

    def test_enrichment_llm_error_falls_back_to_original(self, api_client, db_session):
        _set_enrichment_model(db_session)
        from app.llm_client import LLMError
        with patch("app.routers.search.OpenSearchClient") as MockOS, \
             patch("app.routers.search.LLMClient") as MockLLM:
            MockLLM.return_value.translate.side_effect = LLMError("timeout")
            MockOS.return_value.search.return_value = _os_response([_os_hit("1")])
            resp = api_client.post("/api/search", json={"query": "test", "enrich": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["fallback_used"] is True
