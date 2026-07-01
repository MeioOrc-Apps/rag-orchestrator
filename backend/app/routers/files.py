from __future__ import annotations

import uuid
from datetime import datetime, timezone

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
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


def _file_to_response(f: File, chunks: ChunksSummary | None = None) -> FileResponse:
    return FileResponse(
        id=f.id, path=f.path, filename=f.filename, domain=f.domain,
        file_hash=f.file_hash, file_size_bytes=f.file_size_bytes,
        parse_status=f.parse_status, parse_error=f.parse_error,
        created_at=f.created_at, updated_at=f.updated_at,
        chunks=chunks,
    )


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
    file_ids = [f.id for f in items]

    # Batch-fetch chunk counts grouped by file_id + index_status
    chunk_counts: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if file_ids:
        rows = (
            db.query(Chunk.file_id, Chunk.index_status, func.count().label("cnt"))
            .filter(Chunk.file_id.in_(file_ids))
            .group_by(Chunk.file_id, Chunk.index_status)
            .all()
        )
        for fid, status, cnt in rows:
            chunk_counts[fid][status] = cnt

    def _chunks_summary(fid: uuid.UUID) -> ChunksSummary:
        c = chunk_counts[fid]
        return ChunksSummary(
            total=sum(c.values()),
            done=c.get("done", 0),
            pending=c.get("pending", 0),
            failed=c.get("failed", 0),
            deleted=c.get("deleted", 0),
        )

    return PaginatedResponse(
        items=[_file_to_response(f, _chunks_summary(f.id)) for f in items],
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
    return FileDetailResponse(**_file_to_response(file_row).model_dump(exclude={"chunks"}), chunks=summary)


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
