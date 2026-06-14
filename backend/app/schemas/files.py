import uuid
from datetime import datetime

from pydantic import BaseModel


class ProcessedFileResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    folder_id: uuid.UUID
    source_path: str
    dest_path: str | None
    content_hash: str
    file_type: str
    route: str
    status: str
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
