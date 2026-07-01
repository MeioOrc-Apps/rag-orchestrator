from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Chunk, File
from app.schemas.files import (
    ChunksSummary,
    FileDetailResponse,
    FileResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_file_or_404(file_id: uuid.UUID, db: Session) -> File:
    file_row = db.query(File).filter(File.id == file_id, File.deleted_at.is_(None)).first()
    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")
    return file_row


@router.get("", response_model=PaginatedResponse[FileResponse])
def list_files(
    domain: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FileResponse]:
    q = db.query(File).filter(File.deleted_at.is_(None))
    if domain is not None:
        q = q.filter(File.domain == domain)
    if parse_status is not None:
        q = q.filter(File.parse_status == parse_status)
    total = q.count()
    items = q.order_by(File.created_at.desc()).offset(offset).limit(limit).all()
    return PaginatedResponse(
        items=[FileResponse.model_validate(f) for f in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{file_id}", response_model=FileDetailResponse)
def get_file(file_id: uuid.UUID, db: Session = Depends(get_db)) -> FileDetailResponse:
    file_row = _get_file_or_404(file_id, db)
    chunks = db.query(Chunk).filter(Chunk.file_id == file_row.id).all()
    summary = ChunksSummary(
        total=len(chunks),
        done=sum(1 for c in chunks if c.index_status == "done"),
        pending=sum(1 for c in chunks if c.index_status == "pending"),
        failed=sum(1 for c in chunks if c.index_status == "failed"),
        deleted=sum(1 for c in chunks if c.index_status == "deleted"),
    )
    return FileDetailResponse(**FileResponse.model_validate(file_row).model_dump(), chunks=summary)


@router.delete("/{file_id}", status_code=204)
def delete_file(file_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    file_row = _get_file_or_404(file_id, db)
    now = datetime.now(timezone.utc)
    db.query(Chunk).filter(Chunk.file_id == file_row.id).update(
        {"index_status": "deleted", "updated_at": now}
    )
    file_row.deleted_at = now
    file_row.updated_at = now
    db.commit()


@router.post("/{file_id}/reindex")
def reindex_file(file_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    file_row = _get_file_or_404(file_id, db)
    db.query(Chunk).filter(Chunk.file_id == file_row.id).delete()
    file_row.parse_status = "pending"
    file_row.parse_error = None
    file_row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "queued"}


@router.post("/{file_id}/retranslate")
def retranslate_file(file_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    file_row = _get_file_or_404(file_id, db)
    now = datetime.now(timezone.utc)
    db.query(Chunk).filter(
        Chunk.file_id == file_row.id,
        Chunk.translation_status == "failed",
    ).update({"translation_status": "pending", "translation_error": None, "updated_at": now})
    db.commit()
    return {"status": "queued"}
