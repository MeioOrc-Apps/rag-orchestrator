from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ChunksSummary(BaseModel):
    total: int
    translated: int
    done: int
    pending: int
    failed: int
    deleted: int


class FileResponse(BaseModel):
    id: uuid.UUID
    path: str
    filename: str
    domain: str
    file_hash: str
    file_size_bytes: int
    parse_status: str
    parse_error: str | None = None
    chunks: ChunksSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileDetailResponse(FileResponse):
    chunks: ChunksSummary


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
