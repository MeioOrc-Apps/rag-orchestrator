import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class FileResponse(BaseModel):
    id: uuid.UUID
    path: str
    filename: str
    domain: str
    file_hash: str
    file_size_bytes: int
    parse_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
