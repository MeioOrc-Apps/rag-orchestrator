import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.docling_client import DoclingClient
from app.lightrag_client import LightRAGClient, LightRAGScanError
from app.models import User, WatchedFolder
from app.pipeline.ingestor import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_last_sync_result: dict | None = None


def _default_owner(db: Session) -> User:
    from app.config import Settings
    username = Settings().default_owner_username
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Default owner not seeded")
    return user


def _execute_sync(db: Session) -> dict:
    global _last_sync_result
    from app.config import Settings
    settings = Settings()
    owner = _default_owner(db)

    folders = (
        db.query(WatchedFolder)
        .filter(WatchedFolder.owner_id == owner.id, WatchedFolder.enabled.is_(True))
        .all()
    )

    input_dir = Path(settings.lightrag_input_dir)
    docling = DoclingClient(settings.docling_base_url)
    result = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling)

    scan_triggered = False
    if result["processed"] > 0:
        try:
            lightrag = LightRAGClient(
                settings.lightrag_base_url,
                settings.lightrag_username,
                settings.lightrag_password,
            )
            lightrag.trigger_scan()
            scan_triggered = True
        except (LightRAGScanError, Exception) as exc:
            logger.warning("LightRAG scan failed: %s", exc)

    _last_sync_result = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "processed": result["processed"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "scan_triggered": scan_triggered,
    }
    return _last_sync_result


@router.post("")
def trigger_sync(db: Session = Depends(get_db)):
    return _execute_sync(db)


@router.get("/status")
def sync_status():
    if _last_sync_result is None:
        return {"last_run": None}
    return _last_sync_result


def run_sync_job() -> None:
    """Standalone job called by the scheduler (manages its own DB session)."""
    from app.config import Settings
    from app.database import get_engine, get_session_factory

    settings = Settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    db = factory()
    try:
        _execute_sync(db)
    except Exception as exc:
        logger.error("Scheduled sync failed: %s", exc)
    finally:
        db.close()
        engine.dispose()
