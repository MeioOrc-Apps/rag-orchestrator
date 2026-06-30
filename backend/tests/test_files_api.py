import pytest

pytestmark = pytest.mark.integration


# ── helpers ────────────────────────────────────────────────────────────────────

def _sync(api_client):
    return api_client.post("/api/sync")


def _setup_source(tmp_path, monkeypatch, files: dict[str, str]) -> None:
    """Write files into a tmp source dir and register it as a watched folder."""
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "input"))
    (tmp_path / "input").mkdir(exist_ok=True)
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    for name, content in files.items():
        (src / name).write_text(content)
    return src


# ── response shape ─────────────────────────────────────────────────────────────

def test_list_files_returns_paginated_shape(api_client):
    resp = api_client.get("/api/files")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["items"] == []
    assert data["total"] == 0


def test_list_files_after_sync(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {"note.md": "content"})
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    resp = api_client.get("/api/files")
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "done"
    assert data["items"][0]["route"] == "direct"


# ── pagination ─────────────────────────────────────────────────────────────────

def test_list_files_limit_and_offset(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {
        "a.md": "a", "b.md": "b", "c.md": "c",
    })
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    first = api_client.get("/api/files?limit=2&offset=0").json()
    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert first["limit"] == 2
    assert first["offset"] == 0

    second = api_client.get("/api/files?limit=2&offset=2").json()
    assert second["total"] == 3
    assert len(second["items"]) == 1


def test_list_files_default_limit_is_50(api_client):
    resp = api_client.get("/api/files")
    assert resp.json()["limit"] == 50


def test_list_files_offset_beyond_total_returns_empty_items(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {"x.md": "x"})
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    data = api_client.get("/api/files?offset=999").json()
    assert data["total"] == 1
    assert data["items"] == []


# ── sorting ────────────────────────────────────────────────────────────────────

def test_list_files_sort_by_source_path_asc(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {
        "z_last.md": "z", "a_first.md": "a",
    })
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    data = api_client.get("/api/files?sort_by=source_path&order=asc").json()
    paths = [f["source_path"] for f in data["items"]]
    assert paths == sorted(paths)


def test_list_files_sort_by_source_path_desc(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {
        "z_last.md": "z", "a_first.md": "a",
    })
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    data = api_client.get("/api/files?sort_by=source_path&order=desc").json()
    paths = [f["source_path"] for f in data["items"]]
    assert paths == sorted(paths, reverse=True)


def test_list_files_sort_by_status(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {
        "ok.md": "ok", "bad.xyz": "unknown",
    })
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    data = api_client.get("/api/files?sort_by=status&order=asc").json()
    statuses = [f["status"] for f in data["items"]]
    assert statuses == sorted(statuses)


def test_list_files_invalid_sort_field_returns_422(api_client):
    resp = api_client.get("/api/files?sort_by=nonexistent")
    assert resp.status_code == 422


# ── status filter ──────────────────────────────────────────────────────────────

def test_list_files_filter_by_status(api_client, tmp_path, monkeypatch):
    src = _setup_source(tmp_path, monkeypatch, {
        "ok.md": "ok", "bad.xyz": "unknown",
    })
    api_client.post("/api/folders", json={"host_path": str(src), "dest_subdir": "docs"})
    _sync(api_client)

    done = api_client.get("/api/files?status=done").json()
    assert done["total"] == 1
    assert done["items"][0]["status"] == "done"

    failed = api_client.get("/api/files?status=failed").json()
    assert failed["total"] == 1
    assert failed["items"][0]["error_message"] is not None


# ── folder filter ──────────────────────────────────────────────────────────────

def test_list_files_filter_by_folder_id(api_client, tmp_path, monkeypatch):
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "input"))
    (tmp_path / "input").mkdir()

    src_a = tmp_path / "src_a"
    src_a.mkdir()
    (src_a / "file_a.md").write_text("a")

    src_b = tmp_path / "src_b"
    src_b.mkdir()
    (src_b / "file_b.md").write_text("b")

    resp_a = api_client.post("/api/folders", json={"host_path": str(src_a), "dest_subdir": "a"})
    folder_a_id = resp_a.json()["id"]
    api_client.post("/api/folders", json={"host_path": str(src_b), "dest_subdir": "b"})

    _sync(api_client)

    data = api_client.get(f"/api/files?folder_id={folder_a_id}").json()
    assert data["total"] == 1
    assert data["items"][0]["source_path"].endswith("file_a.md")
