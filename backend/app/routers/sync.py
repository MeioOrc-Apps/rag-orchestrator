from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import User, WatchedFolder
from app.pipeline.ingestor import run_pipeline

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _default_owner(db: Session) -> User:
    from app.config import Settings
    username = Settings().default_owner_username
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Default owner not seeded")
    return user


@router.post("")
def trigger_sync(db: Session = Depends(get_db)):
    from app.config import Settings
    settings = Settings()
    owner = _default_owner(db)

    folders = (
        db.query(WatchedFolder)
        .filter(WatchedFolder.owner_id == owner.id, WatchedFolder.enabled.is_(True))
        .all()
    )

    input_dir = Path(settings.lightrag_input_dir)
    result = run_pipeline(db, folders, owner.id, input_dir)

    return {
        "processed": result["processed"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "scan_triggered": False,
    }
