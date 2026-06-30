import os
import pytest

# Provide defaults for all required env vars so tests don't need a .env file.
# Config tests that need specific values use monkeypatch to override these.
_TEST_DEFAULTS = {
    "DATABASE_URL": "postgresql+psycopg://orchestrator:orchestrator@localhost:5433/orchestrator",
    "DOCLING_BASE_URL": "http://localhost:5001",
    "OPENSEARCH_HOST": "http://localhost:9200",
    "INPUT_DIR": "/tmp/rag_inputs",
    "DEFAULT_OWNER_USERNAME": "sergio",
}
for _k, _v in _TEST_DEFAULTS.items():
    os.environ.setdefault(_k, _v)

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://orchestrator:orchestrator@localhost:5433/orchestrator",
)


@pytest.fixture(scope="session")
def test_db_url():
    return TEST_DB_URL


@pytest.fixture
def clean_schema(test_db_url):
    """Drop and recreate the public schema for a clean slate."""
    from sqlalchemy import create_engine, text

    def _reset(url):
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        engine.dispose()

    _reset(test_db_url)
    yield
    _reset(test_db_url)


@pytest.fixture
def migrated_db(test_db_url, clean_schema):
    """Clean schema + migrations applied. Returns db URL."""
    from alembic.config import Config
    from alembic import command

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")
    return test_db_url


@pytest.fixture
def seeded_db(migrated_db):
    """Migrations + default user seeded. Returns db URL."""
    from app.database import get_engine, get_session_factory
    from app.seed import seed_default_user

    engine = get_engine(migrated_db)
    factory = get_session_factory(engine)
    db = factory()
    seed_default_user(db, "sergio")
    db.close()
    engine.dispose()
    return migrated_db


@pytest.fixture
def db_session(seeded_db):
    """Session against the seeded test DB."""
    from app.database import get_engine, get_session_factory

    engine = get_engine(seeded_db)
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(seeded_db):
    """TestClient with get_db overridden to use the seeded test DB."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db
    from app.database import get_engine, get_session_factory

    engine = get_engine(seeded_db)
    factory = get_session_factory(engine)

    def _override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()
