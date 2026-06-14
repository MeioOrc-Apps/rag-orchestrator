import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import ProcessedFile, User
from app.schemas.files import ProcessedFileResponse

router = APIRouter(prefix="/api/files", tags=["files"])


def _default_owner(db: Session) -> User:
    from app.config import Settings
    username = Settings().default_owner_username
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Default owner not seeded")
    return user


@router.get("", response_model=list[ProcessedFileResponse])
def list_files(
    status: Annotated[str | None, Query()] = None,
    folder_id: Annotated[uuid.UUID | None, Query()] = None,
    db: Session = Depends(get_db),
):
    owner = _default_owner(db)
    q = db.query(ProcessedFile).filter(ProcessedFile.owner_id == owner.id)
    if status is not None:
        q = q.filter(ProcessedFile.status == status)
    if folder_id is not None:
        q = q.filter(ProcessedFile.folder_id == folder_id)
    return q.order_by(ProcessedFile.created_at.desc()).all()
