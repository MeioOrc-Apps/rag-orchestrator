from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Chunk
from app.opensearch_client import OpenSearchClient


def run_delete_job() -> None:
    """Standalone scheduler wrapper — manages its own DB session."""
    import logging
    from app.config import Settings
    from app.database import get_engine, get_session_factory

    logger = logging.getLogger(__name__)
    settings = Settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    db = factory()
    try:
        run_delete(db)
    except Exception as exc:
        logger.error("Scheduled delete job failed: %s", exc)
    finally:
        db.close()
        engine.dispose()


def run_delete(db: Session) -> dict:
    from app.config import Settings
    cfg = Settings()
    client = OpenSearchClient(cfg.opensearch_host, index_prefix=cfg.opensearch_index_prefix)

    chunks = db.query(Chunk).filter(Chunk.index_status == "deleted").all()
    if not chunks:
        return {"deleted_from_os": 0, "deleted_from_db": 0}

    # Split into: need OS delete vs. never indexed
    with_os_id = [c for c in chunks if c.opensearch_id]
    without_os_id = [c for c in chunks if not c.opensearch_id]

    deleted_from_os = 0
    to_hard_delete: list[Chunk] = list(without_os_id)

    # Group by domain and call bulk_delete
    by_domain: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in with_os_id:
        by_domain[chunk.file.domain].append(chunk)

    confirmed_os_ids: set[str] = set()
    for domain, domain_chunks in by_domain.items():
        os_ids = [c.opensearch_id for c in domain_chunks]
        confirmed = client.bulk_delete(domain, os_ids)
        confirmed_os_ids.update(confirmed)
        deleted_from_os += len(confirmed)

    # Hard-delete from DB: only those confirmed by OS, plus ones without os_id
    os_id_to_chunk = {c.opensearch_id: c for c in with_os_id}
    for os_id in confirmed_os_ids:
        if os_id in os_id_to_chunk:
            to_hard_delete.append(os_id_to_chunk[os_id])

    deleted_from_db = 0
    for chunk in to_hard_delete:
        db.delete(chunk)
        deleted_from_db += 1
    db.commit()

    return {"deleted_from_os": deleted_from_os, "deleted_from_db": deleted_from_db}
