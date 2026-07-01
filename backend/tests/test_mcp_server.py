"""Tests for MCP server — separate FastAPI on MCP_PORT, delegates to main API."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mcp_client():
    from fastapi.testclient import TestClient
    from app.mcp_server import mcp_app
    with TestClient(mcp_app) as client:
        yield client


class TestMCPToolList:
    def test_get_root_returns_tool_list(self, mcp_client):
        resp = mcp_client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "tools" in body

    def test_tool_list_has_four_tools(self, mcp_client):
        body = mcp_client.get("/").json()
        names = {t["name"] for t in body["tools"]}
        assert names == {"search", "list_files", "get_stats", "reindex_file"}

    def test_each_tool_has_name_and_description(self, mcp_client):
        body = mcp_client.get("/").json()
        for tool in body["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool


class TestMCPToolCall:
    def test_call_unknown_tool_returns_404(self, mcp_client):
        resp = mcp_client.post("/tools/call", json={"tool": "nonexistent", "arguments": {}})
        assert resp.status_code == 404

    def test_call_returns_result_field(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"results": [], "total": 0, "fallback_used": False}
            mock_resp.status_code = 200
            mock_httpx.post.return_value = mock_resp
            resp = mcp_client.post("/tools/call", json={
                "tool": "search",
                "arguments": {"query": "machine learning"},
            })
        assert resp.status_code == 200
        assert "result" in resp.json()


class TestMCPSearchTool:
    def test_search_delegates_to_main_api(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "results": [{"chunk_id": "1", "content_en": "hello", "score": 0.9}],
                "total": 1,
                "fallback_used": False,
            }
            mock_httpx.post.return_value = mock_resp

            resp = mcp_client.post("/tools/call", json={
                "tool": "search",
                "arguments": {"query": "test query", "domain": "docs"},
            })

        assert resp.status_code == 200
        mock_httpx.post.assert_called_once()
        call_url = mock_httpx.post.call_args[0][0]
        assert "/api/search" in call_url

    def test_search_passes_query_argument(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"results": [], "total": 0, "fallback_used": False}
            mock_httpx.post.return_value = mock_resp

            mcp_client.post("/tools/call", json={
                "tool": "search",
                "arguments": {"query": "neural networks"},
            })

        payload = mock_httpx.post.call_args[1]["json"]
        assert payload["query"] == "neural networks"


class TestMCPListFilesTool:
    def test_list_files_delegates_to_main_api(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}
            mock_httpx.get.return_value = mock_resp

            resp = mcp_client.post("/tools/call", json={
                "tool": "list_files",
                "arguments": {},
            })

        assert resp.status_code == 200
        call_url = mock_httpx.get.call_args[0][0]
        assert "/api/files" in call_url

    def test_list_files_passes_domain_filter(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}
            mock_httpx.get.return_value = mock_resp

            mcp_client.post("/tools/call", json={
                "tool": "list_files",
                "arguments": {"domain": "research"},
            })

        call_kwargs = mock_httpx.get.call_args
        assert "research" in str(call_kwargs)


class TestMCPGetStatsTool:
    def test_get_stats_delegates_to_admin_api(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "files": {"total": 5, "by_parse_status": {}},
                "chunks": {"total": 20, "by_index_status": {}},
            }
            mock_httpx.get.return_value = mock_resp

            resp = mcp_client.post("/tools/call", json={
                "tool": "get_stats",
                "arguments": {},
            })

        assert resp.status_code == 200
        call_url = mock_httpx.get.call_args[0][0]
        assert "/api/admin/stats" in call_url


class TestMCPReindexFileTool:
    def test_reindex_file_resolves_filename_to_id(self, mcp_client):
        file_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with patch("app.mcp_server.httpx") as mock_httpx:
            # GET /api/files?filename=report.md → returns file with id
            list_resp = MagicMock()
            list_resp.status_code = 200
            list_resp.json.return_value = {
                "items": [{"id": file_id, "filename": "report.md", "domain": "docs"}],
                "total": 1, "limit": 50, "offset": 0,
            }
            # POST /api/files/{id}/reindex → 200
            reindex_resp = MagicMock()
            reindex_resp.status_code = 200
            reindex_resp.json.return_value = {"status": "queued"}
            mock_httpx.get.return_value = list_resp
            mock_httpx.post.return_value = reindex_resp

            resp = mcp_client.post("/tools/call", json={
                "tool": "reindex_file",
                "arguments": {"filename": "report.md"},
            })

        assert resp.status_code == 200
        reindex_url = mock_httpx.post.call_args[0][0]
        assert file_id in reindex_url
        assert "reindex" in reindex_url

    def test_reindex_file_not_found_returns_error(self, mcp_client):
        with patch("app.mcp_server.httpx") as mock_httpx:
            list_resp = MagicMock()
            list_resp.status_code = 200
            list_resp.json.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}
            mock_httpx.get.return_value = list_resp

            resp = mcp_client.post("/tools/call", json={
                "tool": "reindex_file",
                "arguments": {"filename": "missing.md"},
            })

        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body["result"] or "not found" in str(body["result"]).lower()
