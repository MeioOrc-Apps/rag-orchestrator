import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import ProcessedFile, User
from app.schemas.files import PaginatedResponse, ProcessedFileResponse

router = APIRouter(prefix="/api/files", tags=["files"])

_SORT_COLUMNS = {
    "created_at": ProcessedFile.created_at,
    "source_path": ProcessedFile.source_path,
    "status": ProcessedFile.status,
}


def _default_owner(db: Session) -> User:
    from app.config import Settings
    username = Settings().default_owner_username
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=500, detail="Default owner not seeded")
    return user


@router.get("", response_model=PaginatedResponse[ProcessedFileResponse])
def list_files(
    status: Annotated[str | None, Query()] = None,
    folder_id: Annotated[uuid.UUID | None, Query()] = None,
    sort_by: Annotated[Literal["created_at", "source_path", "status"], Query()] = "created_at",
    order: Annotated[Literal["asc", "desc"], Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
):
    owner = _default_owner(db)
    q = db.query(ProcessedFile).filter(ProcessedFile.owner_id == owner.id)

    if status is not None:
        q = q.filter(ProcessedFile.status == status)
    if folder_id is not None:
        q = q.filter(ProcessedFile.folder_id == folder_id)

    total = q.count()

    col = _SORT_COLUMNS[sort_by]
    q = q.order_by(asc(col) if order == "asc" else desc(col))
    items = q.offset(offset).limit(limit).all()

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
