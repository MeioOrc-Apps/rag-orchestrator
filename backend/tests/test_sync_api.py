import pytest
from pathlib import Path
from unittest.mock import patch


pytestmark = pytest.mark.integration


@pytest.fixture
def sync_client(seeded_db, tmp_path, monkeypatch):
    """api_client with INPUT_DIR pointing to tmp_path."""
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "input"))
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


def test_sync_returns_scan_result_shape(sync_client):
    client, _ = sync_client
    resp = client.post("/api/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert "scanned" in body
    assert "inserted" in body
    assert "updated" in body
    assert "deleted" in body
    assert "skipped" in body
    assert "last_run" in body


def test_sync_with_no_folders_returns_zero_counts(sync_client):
    client, _ = sync_client
    resp = client.post("/api/sync")
    body = resp.json()
    assert body["inserted"] == 0
    assert body["skipped"] == 0
    assert body["deleted"] == 0


def test_sync_inserts_file_into_files_table(sync_client, seeded_db):
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
    assert body["inserted"] == 1

    from app.database import get_engine, get_session_factory
    from app.models import File
    engine = get_engine(seeded_db)
    factory = get_session_factory(engine)
    db = factory()
    f = db.query(File).filter(File.domain == "docs").first()
    db.close()
    engine.dispose()
    assert f is not None
    assert f.parse_status == "pending"


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
    assert body["inserted"] == 0


def test_status_returns_null_before_first_sync(sync_client):
    import app.routers.sync as sync_mod
    client, _ = sync_client
    original = sync_mod._last_sync_result
    sync_mod._last_sync_result = None
    try:
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        assert resp.json()["last_run"] is None
    finally:
        sync_mod._last_sync_result = original


def test_status_returns_last_sync_after_sync(sync_client):
    client, _ = sync_client
    client.post("/api/sync")
    resp = client.get("/api/sync/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["last_run"] is not None
    assert "inserted" in body


def test_sync_skips_disabled_folders(sync_client):
    client, tmp_path = sync_client
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("content")

    client.post("/api/folders", json={
        "host_path": str(source),
        "dest_subdir": "docs",
        "enabled": False,
    })

    resp = client.post("/api/sync")
    assert resp.json()["inserted"] == 0
