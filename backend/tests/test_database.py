import os
import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


@pytest.fixture
def db_session(test_db_url):
    from app.database import get_engine, get_session_factory
    engine = get_engine(test_db_url)
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_session_opens_and_executes(db_session):
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_session_closes_cleanly(test_db_url):
    from app.database import get_engine, get_session_factory
    engine = get_engine(test_db_url)
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()
    session.execute(text("SELECT 1"))
    session.close()
    engine.dispose()
