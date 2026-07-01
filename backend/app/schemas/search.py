from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    domain: str | None = None
    enrich: bool = True
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchHit(BaseModel):
    chunk_id: str
    file_id: str
    domain: str
    chunk_index: int
    source_language: str
    content_en: str
    content_pt: str
    score: float
    highlights: dict[str, Any] = {}


class SearchResponse(BaseModel):
    results: list[SearchHit]
    total: int
    fallback_used: bool
    query_enriched: str | None = None
