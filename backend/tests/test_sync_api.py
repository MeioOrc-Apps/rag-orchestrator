import pytest
from pathlib import Path
from unittest.mock import patch


pytestmark = pytest.mark.integration


@pytest.fixture
def sync_client(seeded_db, tmp_path, monkeypatch):
    """api_client with LIGHTRAG_INPUT_DIR pointing to tmp_path."""
    monkeypatch.setenv("LIGHTRAG_INPUT_DIR", str(tmp_path / "input"))
    (tmp_path / "input").mkdir()

    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db
    from app.database import get_engine, get_session_factory

    engine = get_engine(seeded_db)
    factory = get_session_factory(engine)

    def _override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        yield client, tmp_path
    app.dependency_overrides.clear()
    engine.dispose()


def test_sync_returns_summary_with_scan_triggered_false(sync_client):
    client, _ = sync_client
    resp = client.post("/api/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert "processed" in body
    assert "skipped" in body
    assert "failed" in body
    assert body["scan_triggered"] is False


def test_sync_with_no_folders_returns_zero_counts(sync_client):
    client, _ = sync_client
    resp = client.post("/api/sync")
    body = resp.json()
    assert body["processed"] == 0
    assert body["skipped"] == 0
    assert body["failed"] == 0


def test_sync_processes_md_file_in_watched_folder(sync_client):
    client, tmp_path = sync_client
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("# Hello")

    client.post("/api/folders", json={
        "host_path": str(source),
        "dest_subdir": "docs",
    })

    resp = client.post("/api/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 1
    assert body["scan_triggered"] is False

    dest = tmp_path / "input" / "docs" / "doc.md"
    assert dest.exists()


def test_sync_deduplicates_on_second_run(sync_client):
    client, tmp_path = sync_client
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("content")

    client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})
    client.post("/api/sync")
    resp = client.post("/api/sync")

    body = resp.json()
    assert body["skipped"] == 1
    assert body["processed"] == 0


def test_sync_skips_disabled_folders(sync_client):
    client, tmp_path = sync_client
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("content")

    created = client.post("/api/folders", json={
        "host_path": str(source),
        "dest_subdir": "docs",
        "enabled": False,
    }).json()

    resp = client.post("/api/sync")
    assert resp.json()["processed"] == 0
