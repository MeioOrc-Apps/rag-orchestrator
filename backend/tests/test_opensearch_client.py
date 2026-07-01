import json
import pytest
from unittest.mock import MagicMock, patch


def _make_client(host="http://localhost:9200", prefix="rag"):
    from app.opensearch_client import OpenSearchClient
    return OpenSearchClient(host=host, index_prefix=prefix)


def _mock_response(status_code: int, body: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ── ensure_index ──────────────────────────────────────────────────────────────

def test_ensure_index_creates_index_when_not_exists():
    client = _make_client()
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        # HEAD returns 404 (not exists), PUT returns 200
        instance.head.return_value = _mock_response(404, {})
        instance.put.return_value = _mock_response(200, {"acknowledged": True})

        result = client.ensure_index("rpg")

    assert result is True
    instance.put.assert_called_once()
    call_url = instance.put.call_args[0][0]
    assert "rag_rpg" in call_url


def test_ensure_index_is_idempotent_when_already_exists():
    client = _make_client()
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.head.return_value = _mock_response(200, {})

        result = client.ensure_index("rpg")

    assert result is True
    instance.put.assert_not_called()


def test_ensure_index_uses_prefix_in_index_name():
    client = _make_client(prefix="myprefix")
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.head.return_value = _mock_response(404, {})
        instance.put.return_value = _mock_response(200, {"acknowledged": True})

        client.ensure_index("docs")

    call_url = instance.put.call_args[0][0]
    assert "myprefix_docs" in call_url


# ── bulk_index ────────────────────────────────────────────────────────────────

def test_bulk_index_returns_successes_and_errors():
    client = _make_client()
    docs = [
        {"chunk_id": "uuid-1", "content_en": "hello", "domain": "rpg", "chunk_index": 0},
        {"chunk_id": "uuid-2", "content_en": "world", "domain": "rpg", "chunk_index": 1},
    ]
    bulk_response = {
        "errors": True,
        "items": [
            {"index": {"_id": "os-id-1", "result": "created", "status": 201, "_index": "rag_rpg"}},
            {"index": {"_id": None, "error": {"reason": "mapping error"}, "status": 400, "_index": "rag_rpg"}},
        ],
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, bulk_response)

        successes, errors = client.bulk_index("rpg", docs)

    assert len(successes) == 1
    assert successes[0] == ("uuid-1", "os-id-1")
    assert len(errors) == 1
    assert errors[0][0] == "uuid-2"
    assert "mapping error" in errors[0][1]


def test_bulk_index_all_success():
    client = _make_client()
    docs = [{"chunk_id": "uid-1", "content_en": "text", "domain": "ti", "chunk_index": 0}]
    bulk_response = {
        "errors": False,
        "items": [{"index": {"_id": "os-1", "result": "created", "status": 201, "_index": "rag_ti"}}],
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, bulk_response)

        successes, errors = client.bulk_index("ti", docs)

    assert len(successes) == 1
    assert errors == []


# ── bulk_delete ───────────────────────────────────────────────────────────────

def test_bulk_delete_returns_confirmed_ids():
    client = _make_client()
    bulk_response = {
        "errors": False,
        "items": [
            {"delete": {"_id": "os-id-1", "result": "deleted", "status": 200}},
            {"delete": {"_id": "os-id-2", "result": "deleted", "status": 200}},
        ],
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, bulk_response)

        confirmed = client.bulk_delete("rpg", ["os-id-1", "os-id-2"])

    assert confirmed == ["os-id-1", "os-id-2"]


def test_bulk_delete_excludes_failed_ids():
    client = _make_client()
    bulk_response = {
        "errors": True,
        "items": [
            {"delete": {"_id": "os-id-1", "result": "deleted", "status": 200}},
            {"delete": {"_id": "os-id-2", "error": {"reason": "not found"}, "status": 404}},
        ],
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, bulk_response)

        confirmed = client.bulk_delete("rpg", ["os-id-1", "os-id-2"])

    assert confirmed == ["os-id-1"]


# ── search ────────────────────────────────────────────────────────────────────

def test_search_returns_hits_with_highlights_and_scores():
    client = _make_client()
    os_response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "os-id-1",
                    "_score": 1.42,
                    "_source": {
                        "chunk_id": "uuid-1",
                        "file_id": "fid-1",
                        "domain": "rpg",
                        "chunk_index": 0,
                        "source_language": "en",
                        "content_en": "sword attack maneuver",
                        "content_pt": "",
                    },
                    "highlight": {"content_en": ["<em>sword</em> attack"]},
                }
            ],
        }
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, os_response)

        results = client.search("sword attack", domain="rpg", limit=5, offset=0)

    assert results["total"] == 1
    assert len(results["hits"]) == 1
    hit = results["hits"][0]
    assert hit["chunk_id"] == "uuid-1"
    assert hit["score"] == 1.42
    assert "sword" in hit["highlight"]


def test_search_with_no_domain_queries_all_indices():
    client = _make_client()
    os_response = {"hits": {"total": {"value": 0}, "hits": []}}
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(200, os_response)

        client.search("query", domain=None, limit=10, offset=0)

    call_url = instance.post.call_args[0][0]
    assert "rag_*" in call_url


# ── get_index_stats ───────────────────────────────────────────────────────────

def test_get_index_stats_returns_docs_count_and_size():
    client = _make_client()
    stats_response = {
        "indices": {
            "rag_rpg": {
                "primaries": {
                    "docs": {"count": 1500},
                    "store": {"size_in_bytes": 5_242_880},  # 5 MB
                }
            }
        }
    }
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = _mock_response(200, stats_response)

        stats = client.get_index_stats("rpg")

    assert stats["docs_count"] == 1500
    assert stats["index_size_mb"] == pytest.approx(5.0, abs=0.1)


def test_get_index_stats_returns_zeros_for_missing_index():
    client = _make_client()
    import httpx
    with patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        resp = _mock_response(404, {"error": "index not found"})
        instance.get.return_value = resp

        stats = client.get_index_stats("nonexistent")

    assert stats["docs_count"] == 0
    assert stats["index_size_mb"] == 0.0
