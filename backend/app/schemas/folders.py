import os
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class FolderCreate(BaseModel):
    host_path: str
    dest_subdir: str
    recursive: bool = True
    enabled: bool = True

    @field_validator("host_path")
    @classmethod
    def host_path_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("host_path cannot be empty")
        return v

    @field_validator("dest_subdir")
    @classmethod
    def dest_subdir_no_traversal(cls, v: str) -> str:
        if os.path.isabs(v):
            raise ValueError("dest_subdir must be a relative path, not absolute")
        parts = v.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError("dest_subdir cannot contain path traversal (..)")
        return v


class FolderUpdate(BaseModel):
    dest_subdir: str | None = None
    recursive: bool | None = None
    enabled: bool | None = None

    @field_validator("dest_subdir", mode="before")
    @classmethod
    def dest_subdir_no_traversal(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if os.path.isabs(v):
            raise ValueError("dest_subdir must be a relative path, not absolute")
        parts = v.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError("dest_subdir cannot contain path traversal (..)")
        return v


class FolderResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    host_path: str
    dest_subdir: str
    recursive: bool
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
