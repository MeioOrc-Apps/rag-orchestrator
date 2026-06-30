import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.jobs.scan_job import run_scan
from app.models import User, WatchedFolder

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
    owner = _default_owner(db)
    folders = (
        db.query(WatchedFolder)
        .filter(WatchedFolder.owner_id == owner.id, WatchedFolder.enabled.is_(True))
        .all()
    )
    result = run_scan(db, folders)
    now = datetime.now(timezone.utc)
    _last_sync_result = {"last_run": now.isoformat(), **result}
    return _last_sync_result


@router.post("")
def trigger_sync(db: Session = Depends(get_db)):
    return _execute_sync(db)


@router.get("/status")
def sync_status():
    if _last_sync_result is not None:
        return _last_sync_result
    return {"last_run": None}


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
