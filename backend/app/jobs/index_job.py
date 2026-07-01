from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Chunk
from app.opensearch_client import OpenSearchClient

_BATCH_SIZE = 100


def run_index(db: Session, batch_size: int = _BATCH_SIZE) -> dict:
    from app.config import Settings
    cfg = Settings()
    client = OpenSearchClient(cfg.opensearch_host, index_prefix=cfg.opensearch_index_prefix)

    chunks = (
        db.query(Chunk)
        .join(Chunk.file)
        .filter(
            Chunk.translation_status.in_(("done", "not_needed")),
            Chunk.index_status == "pending",
        )
        .limit(batch_size)
        .all()
    )

    if not chunks:
        return {"indexed": 0, "failed": 0}

    # Group by domain; call ensure_index once per domain
    by_domain: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        by_domain[chunk.file.domain].append(chunk)

    indexed = failed = 0
    for domain, domain_chunks in by_domain.items():
        client.ensure_index(domain)
        docs = [_chunk_to_doc(c) for c in domain_chunks]
        successes, errors = client.bulk_index(domain, docs)

        success_map = {chunk_id: os_id for chunk_id, os_id in successes}
        error_map = {chunk_id: reason for chunk_id, reason in errors}

        now = datetime.now(timezone.utc)
        for chunk in domain_chunks:
            cid = str(chunk.id)
            if cid in success_map:
                chunk.index_status = "done"
                chunk.opensearch_id = success_map[cid]
                chunk.indexed_at = now
                chunk.index_error = None
                chunk.updated_at = now
                indexed += 1
            elif cid in error_map:
                chunk.index_status = "failed"
                chunk.index_error = error_map[cid]
                chunk.updated_at = now
                failed += 1
        db.commit()

    return {"indexed": indexed, "failed": failed}


def _chunk_to_doc(chunk: Chunk) -> dict:
    return {
        "chunk_id": str(chunk.id),
        "file_id": str(chunk.file_id),
        "domain": chunk.file.domain,
        "chunk_index": chunk.chunk_index,
        "source_language": chunk.source_language,
        "content_pt": chunk.content_original,
        "content_en": chunk.content_en or "",
        "char_count": chunk.char_count,
    }
