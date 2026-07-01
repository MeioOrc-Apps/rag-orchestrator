from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Chunk, File, PipelineSettings, TranslationSettings
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


# ── Settings endpoints ────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    ts = db.query(TranslationSettings).first()
    ps = db.query(PipelineSettings).first()
    return {
        "llm": {
            "translation_model": ts.model if ts else "",
            "enrichment_model": ts.enrichment_model if ts else "",
            "translation_enabled": ts.enabled if ts else False,
            "translation_batch_size": ts.batch_size if ts else 5,
            "translate_workers": ts.translate_workers if ts else 10,
            "prompt_template_en": ts.prompt_template_en if ts else "",
            "prompt_template_pt": ts.prompt_template_pt if ts else "",
            "prompt_enrichment": ts.prompt_enrichment if ts else "",
        },
        "pipeline": {
            "chunk_size": ps.chunk_size if ps else 1000,
            "chunk_overlap": ps.chunk_overlap if ps else 100,
            "parse_batch_size": ps.parse_batch_size if ps else 20,
            "max_translation_retries": ps.max_translation_retries if ps else 3,
        },
    }


class LLMSettingsUpdate(BaseModel):
    translation_model: str | None = None
    enrichment_model: str | None = None
    translation_enabled: bool | None = None
    translation_batch_size: int | None = None
    translate_workers: int | None = None
    prompt_template_en: str | None = None
    prompt_template_pt: str | None = None
    prompt_enrichment: str | None = None


class PipelineSettingsUpdate(BaseModel):
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    parse_batch_size: int | None = None
    max_translation_retries: int | None = None


class SettingsUpdate(BaseModel):
    llm: LLMSettingsUpdate | None = None
    pipeline: PipelineSettingsUpdate | None = None


@router.put("/settings")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    if body.llm is not None:
        ts = db.query(TranslationSettings).first()
        if ts is None:
            raise HTTPException(status_code=404, detail="translation_settings row not found")
        llm = body.llm
        if llm.translation_model is not None:
            ts.model = llm.translation_model
        if llm.enrichment_model is not None:
            ts.enrichment_model = llm.enrichment_model
        if llm.translation_enabled is not None:
            ts.enabled = llm.translation_enabled
        if llm.translation_batch_size is not None:
            ts.batch_size = llm.translation_batch_size
        if llm.translate_workers is not None:
            ts.translate_workers = llm.translate_workers
        if llm.prompt_template_en is not None:
            ts.prompt_template_en = llm.prompt_template_en
        if llm.prompt_template_pt is not None:
            ts.prompt_template_pt = llm.prompt_template_pt
        if llm.prompt_enrichment is not None:
            ts.prompt_enrichment = llm.prompt_enrichment
        ts.updated_at = now

    if body.pipeline is not None:
        ps = db.query(PipelineSettings).first()
        if ps is None:
            raise HTTPException(status_code=404, detail="pipeline_settings row not found")
        pipe = body.pipeline
        if pipe.chunk_size is not None:
            ps.chunk_size = pipe.chunk_size
        if pipe.chunk_overlap is not None:
            ps.chunk_overlap = pipe.chunk_overlap
        if pipe.parse_batch_size is not None:
            ps.parse_batch_size = pipe.parse_batch_size
        if pipe.max_translation_retries is not None:
            ps.max_translation_retries = pipe.max_translation_retries
        ps.updated_at = now

    db.commit()
    return get_settings(db)
