from typing import Generator

from sqlalchemy.orm import Session

from app.database import get_engine, get_session_factory

_engine = None
_session_factory = None


def _ensure_engine():
    global _engine, _session_factory
    if _engine is None:
        from app.config import Settings
        settings = Settings()
        _engine = get_engine(settings.database_url)
        _session_factory = get_session_factory(_engine)


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    db = _session_factory()
    try:
        yield db
    finally:
        db.close()
