"""
Real OpenSearch integration tests.
Require TEST_OPENSEARCH_HOST env var to be set (e.g. http://192.168.3.100:9200).
Skipped automatically if the env var is absent or the host is unreachable.
Run: TEST_OPENSEARCH_HOST=http://192.168.3.100:9200 pytest -m integration_opensearch
"""
import os
import uuid
import pytest
import httpx

pytestmark = pytest.mark.integration_opensearch

_HOST_FROM_ENV = os.getenv("TEST_OPENSEARCH_HOST")

if not _HOST_FROM_ENV:
    pytest.skip("TEST_OPENSEARCH_HOST not set", allow_module_level=True)

OPENSEARCH_HOST = _HOST_FROM_ENV


@pytest.fixture
def client():
    from app.opensearch_client import OpenSearchClient
    return OpenSearchClient(host=OPENSEARCH_HOST, index_prefix="rag_test")


@pytest.fixture(autouse=True)
def cleanup_test_index(client):
    domain = "inttest"
    yield
    import httpx
    with httpx.Client(timeout=10) as hc:
        hc.delete(f"{OPENSEARCH_HOST}/rag_test_{domain}")


def test_ensure_index_creates_and_is_idempotent(client):
    result1 = client.ensure_index("inttest")
    result2 = client.ensure_index("inttest")
    assert result1 is True
    assert result2 is True


def test_bulk_index_and_search_round_trip(client):
    client.ensure_index("inttest")
    test_id = str(uuid.uuid4())
    docs = [
        {
            "chunk_id": test_id,
            "file_id": str(uuid.uuid4()),
            "filename": "test.md",
            "domain": "inttest",
            "chunk_index": 0,
            "source_language": "en",
            "content_en": "the wizard casts a fireball spell",
            "content_pt": None,
            "indexed_at": "2026-06-30T00:00:00Z",
        }
    ]
    successes, errors = client.bulk_index("inttest", docs)
    assert errors == []
    assert len(successes) == 1
    assert successes[0][0] == test_id

    import time
    time.sleep(1)  # allow index refresh

    results = client.search("fireball", domain="inttest", limit=5, offset=0)
    assert results["total"] >= 1
    chunk_ids = [h["chunk_id"] for h in results["hits"]]
    assert test_id in chunk_ids


def test_bulk_delete_removes_document(client):
    client.ensure_index("inttest")
    test_id = str(uuid.uuid4())
    docs = [
        {
            "chunk_id": test_id,
            "file_id": str(uuid.uuid4()),
            "filename": "del_test.md",
            "domain": "inttest",
            "chunk_index": 0,
            "source_language": "en",
            "content_en": "document to be deleted",
            "content_pt": None,
            "indexed_at": "2026-06-30T00:00:00Z",
        }
    ]
    successes, _ = client.bulk_index("inttest", docs)
    os_id = successes[0][1]

    import time
    time.sleep(1)

    confirmed = client.bulk_delete("inttest", [os_id])
    assert os_id in confirmed


def test_get_index_stats_returns_counts(client):
    client.ensure_index("inttest")
    stats = client.get_index_stats("inttest")
    assert "docs_count" in stats
    assert "index_size_mb" in stats
    assert stats["docs_count"] >= 0


def test_get_index_stats_nonexistent_returns_zeros(client):
    stats = client.get_index_stats("nonexistent_domain_xyz")
    assert stats["docs_count"] == 0
    assert stats["index_size_mb"] == 0.0
