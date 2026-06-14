import pytest


pytestmark = pytest.mark.integration


def test_list_files_returns_empty_initially(api_client):
    resp = api_client.get("/api/files")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_files_after_sync(api_client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTRAG_INPUT_DIR", str(tmp_path / "input"))
    (tmp_path / "input").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    (source / "note.md").write_text("content")

    from unittest.mock import patch
    api_client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})
    with patch("app.routers.sync.LightRAGClient"):
        api_client.post("/api/sync")

    resp = api_client.get("/api/files")
    assert resp.status_code == 200
    files = resp.json()
    assert len(files) == 1
    assert files[0]["status"] == "done"
    assert files[0]["route"] == "direct"


def test_list_files_filter_by_status(api_client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIGHTRAG_INPUT_DIR", str(tmp_path / "input"))
    (tmp_path / "input").mkdir()
    source = tmp_path / "src"
    source.mkdir()
    (source / "ok.md").write_text("ok")
    (source / "bad.xyz").write_text("unknown")

    from unittest.mock import patch
    api_client.post("/api/folders", json={"host_path": str(source), "dest_subdir": "docs"})
    with patch("app.routers.sync.LightRAGClient"):
        api_client.post("/api/sync")

    resp_done = api_client.get("/api/files?status=done")
    assert len(resp_done.json()) == 1

    resp_failed = api_client.get("/api/files?status=failed")
    assert len(resp_failed.json()) == 1
    assert resp_failed.json()[0]["error_message"] is not None
