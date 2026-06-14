import os
import pytest


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://orchestrator:orchestrator@localhost:5433/orchestrator",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integration" in item.keywords:
            if not os.getenv("TEST_DATABASE_URL") and "5433" not in TEST_DB_URL:
                item.add_marker(
                    pytest.mark.skip(reason="TEST_DATABASE_URL not set")
                )


@pytest.fixture(scope="session")
def test_db_url():
    return TEST_DB_URL


@pytest.fixture
def clean_schema(test_db_url):
    """Drop and recreate the public schema for a clean slate."""
    from sqlalchemy import create_engine, text
    engine = create_engine(test_db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    engine.dispose()
    yield
    engine = create_engine(test_db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    engine.dispose()
