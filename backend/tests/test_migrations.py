import os
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.integration


@pytest.fixture
def alembic_cfg(test_db_url, clean_schema):
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    return cfg


def test_migration_creates_users_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    engine.dispose()
    assert "users" in inspector.get_table_names()


def test_migration_creates_watched_folders_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    engine.dispose()
    assert "watched_folders" in inspector.get_table_names()


def test_migration_creates_processed_files_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    engine.dispose()
    assert "processed_files" in inspector.get_table_names()


def test_migration_processed_files_has_unique_constraint(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    constraints = inspector.get_unique_constraints("processed_files")
    engine.dispose()
    names = [c["name"] for c in constraints]
    assert "uq_owner_path_hash" in names


def test_migration_downgrade_removes_all_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "users" not in tables
    assert "watched_folders" not in tables
    assert "processed_files" not in tables
