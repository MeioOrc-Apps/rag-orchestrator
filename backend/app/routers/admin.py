from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Chunk, File
from app.opensearch_client import OpenSearchClient

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _os_client() -> OpenSearchClient:
    from app.config import Settings
    cfg = Settings()
    return OpenSearchClient(cfg.opensearch_host, index_prefix=cfg.opensearch_index_prefix)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> dict:
    files = db.query(File).filter(File.deleted_at.is_(None)).all()
    files_by_status: dict[str, int] = defaultdict(int)
    for f in files:
        files_by_status[f.parse_status] += 1

    chunks = db.query(Chunk).all()
    chunks_by_index: dict[str, int] = defaultdict(int)
    chunks_by_translation: dict[str, int] = defaultdict(int)
    for c in chunks:
        chunks_by_index[c.index_status] += 1
        chunks_by_translation[c.translation_status] += 1

    return {
        "files": {
            "total": len(files),
            "by_parse_status": dict(files_by_status),
        },
        "chunks": {
            "total": len(chunks),
            "by_index_status": dict(chunks_by_index),
            "by_translation_status": dict(chunks_by_translation),
        },
    }


@router.get("/failed")
def get_failed(db: Session = Depends(get_db)) -> dict:
    failed_files = (
        db.query(File)
        .filter(File.parse_status == "failed", File.deleted_at.is_(None))
        .all()
    )
    failed_chunks = (
        db.query(Chunk)
        .filter(
            (Chunk.translation_status == "failed") | (Chunk.index_status == "failed")
        )
        .all()
    )
    return {
        "failed_files": [
            {"id": str(f.id), "path": f.path, "parse_error": f.parse_error}
            for f in failed_files
        ],
        "failed_chunks": [
            {
                "id": str(c.id),
                "file_id": str(c.file_id),
                "translation_status": c.translation_status,
                "index_status": c.index_status,
                "translation_error": c.translation_error,
                "index_error": c.index_error,
            }
            for c in failed_chunks
        ],
    }


@router.post("/retry-failed")
def retry_failed(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)

    files_reset = (
        db.query(File)
        .filter(File.parse_status == "failed", File.deleted_at.is_(None))
        .update({"parse_status": "pending", "parse_error": None, "updated_at": now})
    )
    chunks_translation_reset = (
        db.query(Chunk)
        .filter(Chunk.translation_status == "failed")
        .update({"translation_status": "pending", "translation_error": None, "updated_at": now})
    )
    chunks_index_reset = (
        db.query(Chunk)
        .filter(Chunk.index_status == "failed")
        .update({"index_status": "pending", "index_error": None, "updated_at": now})
    )
    db.commit()
    return {
        "files_reset": files_reset,
        "chunks_translation_reset": chunks_translation_reset,
        "chunks_index_reset": chunks_index_reset,
    }


@router.post("/reindex-all")
def reindex_all(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    db.query(Chunk).delete()
    files_reset = (
        db.query(File)
        .filter(File.deleted_at.is_(None))
        .update({"parse_status": "pending", "parse_error": None, "updated_at": now})
    )
    db.commit()
    return {"files_reset": files_reset, "chunks_deleted": True}


@router.post("/forcemerge")
def forcemerge(db: Session = Depends(get_db)) -> dict:
    client = _os_client()
    domains = [
        row[0]
        for row in db.query(File.domain).filter(File.deleted_at.is_(None)).distinct().all()
    ]
    for domain in domains:
        client.forcemerge(domain)
    return {"domains_merged": domains}
