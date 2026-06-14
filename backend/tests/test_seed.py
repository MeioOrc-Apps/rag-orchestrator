import pytest
from alembic.config import Config
from alembic import command
import os


pytestmark = pytest.mark.integration


@pytest.fixture
def migrated_db(test_db_url, clean_schema):
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")
    return test_db_url


@pytest.fixture
def db_session(migrated_db):
    from app.database import get_engine, get_session_factory
    engine = get_engine(migrated_db)
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_seed_creates_default_user(db_session):
    from app.seed import seed_default_user
    from app.models import User

    user = seed_default_user(db_session, "sergio")

    assert user.id is not None
    assert user.username == "sergio"
    assert db_session.query(User).count() == 1


def test_seed_is_idempotent(db_session):
    from app.seed import seed_default_user
    from app.models import User

    user1 = seed_default_user(db_session, "sergio")
    user2 = seed_default_user(db_session, "sergio")

    assert user1.id == user2.id
    assert db_session.query(User).count() == 1


def test_seed_uses_default_owner_username_from_config(db_session, monkeypatch):
    from app.seed import seed_from_config
    from app.models import User

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
    monkeypatch.setenv("DOCLING_BASE_URL", "http://x")
    monkeypatch.setenv("LIGHTRAG_BASE_URL", "http://x")
    monkeypatch.setenv("LIGHTRAG_USERNAME", "x")
    monkeypatch.setenv("LIGHTRAG_PASSWORD", "x")
    monkeypatch.setenv("LIGHTRAG_INPUT_DIR", "/x")
    monkeypatch.setenv("DEFAULT_OWNER_USERNAME", "admin")

    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)

    user = seed_from_config(db_session)
    assert user.username == "admin"
    assert db_session.query(User).count() == 1
