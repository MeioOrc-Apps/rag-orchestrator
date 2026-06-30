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


def test_migration_keeps_all_original_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "users" in tables
    assert "watched_folders" in tables
    assert "processed_files" in tables
    assert "sync_state" in tables


def test_migration_creates_files_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "files" in tables


def test_migration_creates_chunks_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "chunks" in tables


def test_migration_creates_translation_settings_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "translation_settings" in tables


def test_migration_creates_search_query_log_table(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "search_query_log" in tables


def test_migration_seeds_translation_settings(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM translation_settings")).scalar()
        row = conn.execute(
            text("SELECT model, target_language FROM translation_settings LIMIT 1")
        ).fetchone()
    engine.dispose()
    assert count == 1
    assert row.model == "local:qwen2.5:7b"
    assert row.target_language == "en"


def test_migration_seed_is_idempotent(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM translation_settings")).scalar()
    engine.dispose()
    assert count == 1


def test_migration_downgrade_removes_new_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "-1")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "files" not in tables
    assert "chunks" not in tables
    assert "translation_settings" not in tables
    assert "search_query_log" not in tables
    assert "processed_files" in tables
    assert "sync_state" in tables


def test_full_upgrade_downgrade_upgrade_is_clean(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    engine.dispose()
    assert "files" in tables
    assert "chunks" in tables
    assert "users" in tables
    assert "watched_folders" in tables
