import uuid
import pytest


pytestmark = pytest.mark.integration


class TestPostFolder:
    def test_create_folder_returns_201(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/tmp/docs",
            "dest_subdir": "docs",
        })
        assert resp.status_code == 201

    def test_create_folder_returns_body_with_id(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/data/books",
            "dest_subdir": "books",
        })
        body = resp.json()
        assert "id" in body
        assert body["host_path"] == "/data/books"
        assert body["dest_subdir"] == "books"
        assert body["recursive"] is True
        assert body["enabled"] is True

    def test_create_folder_respects_optional_fields(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/data/pdfs",
            "dest_subdir": "pdfs",
            "recursive": False,
            "enabled": False,
        })
        body = resp.json()
        assert body["recursive"] is False
        assert body["enabled"] is False

    def test_empty_host_path_returns_422(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "",
            "dest_subdir": "docs",
        })
        assert resp.status_code == 422

    def test_whitespace_only_host_path_returns_422(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "   ",
            "dest_subdir": "docs",
        })
        assert resp.status_code == 422

    def test_dest_subdir_with_dotdot_returns_422(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/data/docs",
            "dest_subdir": "../secret",
        })
        assert resp.status_code == 422

    def test_dest_subdir_with_dotdot_nested_returns_422(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/data/docs",
            "dest_subdir": "sub/../../../etc",
        })
        assert resp.status_code == 422

    def test_dest_subdir_with_absolute_path_returns_422(self, api_client):
        resp = api_client.post("/api/folders", json={
            "host_path": "/data/docs",
            "dest_subdir": "/absolute/path",
        })
        assert resp.status_code == 422


class TestGetFolders:
    def test_list_folders_returns_empty_initially(self, api_client):
        resp = api_client.get("/api/folders")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_folders_returns_created_folder(self, api_client):
        api_client.post("/api/folders", json={"host_path": "/data/a", "dest_subdir": "a"})
        api_client.post("/api/folders", json={"host_path": "/data/b", "dest_subdir": "b"})
        resp = api_client.get("/api/folders")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetFolderById:
    def test_get_folder_by_id_returns_detail(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/x",
            "dest_subdir": "x",
        }).json()
        resp = api_client.get(f"/api/folders/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_folder_nonexistent_returns_404(self, api_client):
        resp = api_client.get(f"/api/folders/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestPatchFolder:
    def test_patch_updates_enabled(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/y",
            "dest_subdir": "y",
        }).json()
        resp = api_client.patch(f"/api/folders/{created['id']}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_updates_recursive(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/z",
            "dest_subdir": "z",
        }).json()
        resp = api_client.patch(f"/api/folders/{created['id']}", json={"recursive": False})
        assert resp.json()["recursive"] is False

    def test_patch_updates_dest_subdir(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/w",
            "dest_subdir": "old",
        }).json()
        resp = api_client.patch(f"/api/folders/{created['id']}", json={"dest_subdir": "new"})
        assert resp.json()["dest_subdir"] == "new"

    def test_patch_nonexistent_returns_404(self, api_client):
        resp = api_client.patch(f"/api/folders/{uuid.uuid4()}", json={"enabled": False})
        assert resp.status_code == 404


class TestDeleteFolder:
    def test_delete_folder_returns_204(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/del",
            "dest_subdir": "del",
        }).json()
        resp = api_client.delete(f"/api/folders/{created['id']}")
        assert resp.status_code == 204

    def test_get_after_delete_returns_404(self, api_client):
        created = api_client.post("/api/folders", json={
            "host_path": "/data/del2",
            "dest_subdir": "del2",
        }).json()
        api_client.delete(f"/api/folders/{created['id']}")
        resp = api_client.get(f"/api/folders/{created['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, api_client):
        resp = api_client.delete(f"/api/folders/{uuid.uuid4()}")
        assert resp.status_code == 404
