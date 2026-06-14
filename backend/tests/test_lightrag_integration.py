import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


pytestmark = pytest.mark.integration


@pytest.fixture
def sync_client_with_lightrag(seeded_db, tmp_path, monkeypatch):
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


def test_sync_calls_trigger_scan_when_files_processed(sync_client_with_lightrag):
    client, tmp_path = sync_client_with_lightrag
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("content")
    client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})

    with patch("app.routers.sync.LightRAGClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        resp = client.post("/api/sync")

    assert resp.status_code == 200
    assert resp.json()["scan_triggered"] is True
    mock_instance.trigger_scan.assert_called_once()


def test_sync_does_not_call_trigger_scan_when_nothing_processed(sync_client_with_lightrag):
    client, tmp_path = sync_client_with_lightrag

    with patch("app.routers.sync.LightRAGClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        resp = client.post("/api/sync")

    assert resp.json()["scan_triggered"] is False
    mock_instance.trigger_scan.assert_not_called()


def test_sync_scan_triggered_false_when_all_skipped(sync_client_with_lightrag):
    client, tmp_path = sync_client_with_lightrag
    source = tmp_path / "source"
    source.mkdir()
    (source / "doc.md").write_text("content")
    client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})

    with patch("app.routers.sync.LightRAGClient"):
        client.post("/api/sync")

    with patch("app.routers.sync.LightRAGClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        resp = client.post("/api/sync")

    assert resp.json()["scan_triggered"] is False
    mock_instance.trigger_scan.assert_not_called()


def test_sync_scan_triggered_false_when_lightrag_fails(sync_client_with_lightrag):
    client, tmp_path = sync_client_with_lightrag
    source = tmp_path / "source2"
    source.mkdir()
    (source / "new.md").write_text("new content")
    client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs2"})

    with patch("app.routers.sync.LightRAGClient") as MockClient:
        from app.lightrag_client import LightRAGScanError
        mock_instance = MagicMock()
        mock_instance.trigger_scan.side_effect = LightRAGScanError("unreachable")
        MockClient.return_value = mock_instance

        resp = client.post("/api/sync")

    assert resp.status_code == 200
    assert resp.json()["scan_triggered"] is False
