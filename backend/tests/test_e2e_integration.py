"""End-to-end integration tests.

Require all three services running (see docker-compose.integration.yml).

Run with:
    pytest tests/test_e2e_integration.py -v -m e2e
"""
import os
import pytest
import httpx

DOCLING_URL = os.getenv("DOCLING_BASE_URL", "http://localhost:5001")
LIGHTRAG_URL = os.getenv("LIGHTRAG_BASE_URL", "http://localhost:9621")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8000")
LIGHTRAG_USER = os.getenv("LIGHTRAG_USERNAME", "admin")
LIGHTRAG_PASS = os.getenv("LIGHTRAG_PASSWORD", "admin123")


# ---------------------------------------------------------------------------
# Docling
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_docling_health():
    r = httpx.get(f"{DOCLING_URL}/health", timeout=10)
    assert r.status_code == 200


@pytest.mark.e2e
def test_docling_converts_url_to_markdown():
    """Convert a small public PDF via URL (requires internet in container)."""
    payload = {
        "sources": [
            {
                "kind": "http",
                "url": "https://arxiv.org/pdf/2501.17887",
            }
        ],
        "options": {
            "to_formats": ["md"],
            "do_ocr": False,
            "pdf_backend": "dlparse_v2",
        },
    }
    r = httpx.post(
        f"{DOCLING_URL}/v1/convert/source",
        json=payload,
        timeout=300,  # first call downloads models
    )
    assert r.status_code == 200
    body = r.json()
    md = body["document"]["md_content"]
    assert isinstance(md, str)
    assert len(md) > 100


# ---------------------------------------------------------------------------
# LightRAG
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_lightrag_health():
    r = httpx.get(f"{LIGHTRAG_URL}/health", timeout=10)
    assert r.status_code == 200


@pytest.mark.e2e
def test_lightrag_login_returns_token():
    r = httpx.post(
        f"{LIGHTRAG_URL}/login",
        data={"username": LIGHTRAG_USER, "password": LIGHTRAG_PASS},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert len(body["access_token"]) > 10


@pytest.mark.e2e
def test_lightrag_scan_with_valid_token():
    # login first
    login = httpx.post(
        f"{LIGHTRAG_URL}/login",
        data={"username": LIGHTRAG_USER, "password": LIGHTRAG_PASS},
        timeout=10,
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = httpx.post(
        f"{LIGHTRAG_URL}/documents/scan",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    # 200 or 202 — scan queued/started
    assert r.status_code in (200, 202)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_orchestrator_sync_status():
    r = httpx.get(f"{ORCHESTRATOR_URL}/api/sync/status", timeout=10)
    assert r.status_code == 200


@pytest.mark.e2e
def test_orchestrator_folders_crud():
    # create
    r = httpx.post(
        f"{ORCHESTRATOR_URL}/api/folders",
        json={"host_path": "/data/inputs/test-e2e", "dest_subdir": "e2e"},
        timeout=10,
    )
    assert r.status_code == 201
    folder_id = r.json()["id"]

    # list
    r = httpx.get(f"{ORCHESTRATOR_URL}/api/folders", timeout=10)
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()]
    assert folder_id in ids

    # delete
    r = httpx.delete(f"{ORCHESTRATOR_URL}/api/folders/{folder_id}", timeout=10)
    assert r.status_code == 204


@pytest.mark.e2e
def test_orchestrator_sync_pipeline_with_live_services():
    """Full pipeline: drop a .md file into the container volume → sync → check file recorded.

    The LIGHTRAG_INPUT_DIR is a Docker volume, not a host path — we write the
    test file via `docker exec` so it lands inside the container's filesystem.
    Set BACKEND_CONTAINER to override the container name (default: rag-integration-backend-1).
    """
    import subprocess

    container = os.getenv("BACKEND_CONTAINER", "rag-integration-backend-1")
    test_dir = "/data/inputs/e2e-pipeline-test"
    test_file = f"{test_dir}/hello.md"

    # create dir + write test file inside the backend container
    subprocess.run(
        ["docker", "exec", container, "sh", "-c",
         f"mkdir -p {test_dir} && printf '# Hello\\nE2E integration test document.' > {test_file}"],
        check=True,
    )

    try:
        # register the folder with the orchestrator
        r = httpx.post(
            f"{ORCHESTRATOR_URL}/api/folders",
            json={"host_path": test_dir, "dest_subdir": "e2e-pipeline"},
            timeout=10,
        )
        assert r.status_code == 201
        folder_id = r.json()["id"]

        # trigger sync
        r = httpx.post(f"{ORCHESTRATOR_URL}/api/sync", timeout=60)
        assert r.status_code == 200
        result = r.json()
        assert result["processed"] >= 1 or result["skipped"] >= 1

        # check file recorded
        r = httpx.get(f"{ORCHESTRATOR_URL}/api/files", timeout=10)
        assert r.status_code == 200
        paths = [f["source_path"] for f in r.json()["items"]]
        assert test_file in paths

        # cleanup
        httpx.delete(f"{ORCHESTRATOR_URL}/api/folders/{folder_id}", timeout=10)
    finally:
        subprocess.run(
            ["docker", "exec", container, "rm", "-rf", test_dir],
            check=False,
        )
