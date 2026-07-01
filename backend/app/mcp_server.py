"""MCP (Model Context Protocol) server — separate FastAPI app on MCP_PORT.

Delegates all tool calls to the main API via httpx.
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

mcp_app = FastAPI(title="RAG Orchestrator MCP Server")


def _main_url(path: str) -> str:
    from app.config import Settings
    cfg = Settings()
    # Main API runs on same host, different port (8000 by default)
    # In tests this is overridable; in production both run in same process
    # We use the internal base URL so MCP can reach the main app.
    base = getattr(cfg, "main_api_url", "http://localhost:8000")
    return f"{base}{path}"


_TOOLS = [
    {
        "name": "search",
        "description": "Search the RAG knowledge base using a natural language query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "domain": {"type": "string", "description": "Optional domain filter"},
                "enrich": {"type": "boolean", "description": "LLM query enrichment", "default": True},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
                "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_files",
        "description": "List files tracked by the RAG orchestrator.",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Optional domain filter"},
                "parse_status": {"type": "string", "description": "Filter by parse status"},
                "limit": {"type": "integer", "default": 50},
                "offset": {"type": "integer", "default": 0},
            },
        },
    },
    {
        "name": "get_stats",
        "description": "Get pipeline statistics (file and chunk counts by status).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "reindex_file",
        "description": "Reindex a file by filename — resolves name to ID then triggers reindex.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to reindex"},
            },
            "required": ["filename"],
        },
    },
]

_TOOL_MAP = {t["name"]: t for t in _TOOLS}


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


@mcp_app.get("/")
def list_tools() -> dict:
    return {"tools": _TOOLS}


@mcp_app.post("/tools/call")
def call_tool(req: ToolCallRequest) -> dict:
    if req.tool not in _TOOL_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {req.tool!r}")
    result = _dispatch(req.tool, req.arguments)
    return {"result": result}


def _dispatch(tool: str, args: dict):
    if tool == "search":
        return _tool_search(args)
    if tool == "list_files":
        return _tool_list_files(args)
    if tool == "get_stats":
        return _tool_get_stats()
    if tool == "reindex_file":
        return _tool_reindex_file(args)


def _tool_search(args: dict):
    payload = {
        "query": args["query"],
        "enrich": args.get("enrich", True),
        "limit": args.get("limit", 10),
        "offset": args.get("offset", 0),
    }
    if "domain" in args:
        payload["domain"] = args["domain"]
    resp = httpx.post(_main_url("/api/search"), json=payload)
    return resp.json()


def _tool_list_files(args: dict):
    params = {}
    if "domain" in args:
        params["domain"] = args["domain"]
    if "parse_status" in args:
        params["parse_status"] = args["parse_status"]
    params["limit"] = args.get("limit", 50)
    params["offset"] = args.get("offset", 0)
    resp = httpx.get(_main_url("/api/files"), params=params)
    return resp.json()


def _tool_get_stats():
    resp = httpx.get(_main_url("/api/admin/stats"))
    return resp.json()


def _tool_reindex_file(args: dict):
    filename = args["filename"]
    # Resolve filename → id
    resp = httpx.get(_main_url("/api/files"), params={"limit": 200})
    data = resp.json()
    items = data.get("items", [])
    match = next((f for f in items if f["filename"] == filename), None)
    if match is None:
        return {"error": f"File not found: {filename!r}"}
    file_id = match["id"]
    reindex_resp = httpx.post(_main_url(f"/api/files/{file_id}/reindex"))
    return reindex_resp.json()
