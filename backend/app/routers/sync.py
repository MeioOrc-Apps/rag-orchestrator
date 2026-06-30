import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.docling_client import DoclingClient
from app.models import SyncState, User, WatchedFolder
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


def _execute_sync(db: Session, retry_failed: bool = True) -> dict:
    global _last_sync_result
    from app.config import Settings
    settings = Settings()
    owner = _default_owner(db)

    folders = (
        db.query(WatchedFolder)
        .filter(WatchedFolder.owner_id == owner.id, WatchedFolder.enabled.is_(True))
        .all()
    )

    input_dir = Path(settings.input_dir)
    docling = DoclingClient(settings.docling_base_url)
    result = run_pipeline(db, folders, owner.id, input_dir, docling_client=docling, retry_failed=retry_failed)

    scan_triggered = False
    now = datetime.now(timezone.utc)
    _last_sync_result = {
        "last_run": now.isoformat(),
        "processed": result["processed"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "scan_triggered": scan_triggered,
    }
    _persist_sync_state(db, now, result, scan_triggered)
    return _last_sync_result


def _persist_sync_state(db: Session, now: datetime, result: dict, scan_triggered: bool) -> None:
    state = db.query(SyncState).filter(SyncState.id == 1).first()
    if state is None:
        state = SyncState(id=1)
        db.add(state)
    state.last_run = now
    state.processed = result["processed"]
    state.skipped = result["skipped"]
    state.failed = result["failed"]
    state.scan_triggered = scan_triggered
    db.commit()


@router.post("")
def trigger_sync(db: Session = Depends(get_db)):
    return _execute_sync(db)


@router.get("/status")
def sync_status(db: Session = Depends(get_db)):
    if _last_sync_result is not None:
        return _last_sync_result
    state = db.query(SyncState).filter(SyncState.id == 1).first()
    if state is None or state.last_run is None:
        return {"last_run": None}
    return {
        "last_run": state.last_run.isoformat(),
        "processed": state.processed,
        "skipped": state.skipped,
        "failed": state.failed,
        "scan_triggered": state.scan_triggered,
    }


def run_sync_job() -> None:
    """Standalone job called by the scheduler (manages its own DB session)."""
    from app.config import Settings
    from app.database import get_engine, get_session_factory

    settings = Settings()
    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)
    db = factory()
    try:
        _execute_sync(db, retry_failed=False)
    except Exception as exc:
        logger.error("Scheduled sync failed: %s", exc)
    finally:
        db.close()
        engine.dispose()
