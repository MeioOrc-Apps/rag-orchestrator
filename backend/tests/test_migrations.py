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


def _tables(url: str) -> list[str]:
    engine = create_engine(url)
    tables = inspect(engine).get_table_names()
    engine.dispose()
    return tables


# ── head state (after all migrations) ────────────────────────────────────────

def test_head_has_core_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    tables = _tables(test_db_url)
    assert "users" in tables
    assert "watched_folders" in tables


def test_head_has_opensearch_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    tables = _tables(test_db_url)
    assert "files" in tables
    assert "chunks" in tables
    assert "translation_settings" in tables
    assert "search_query_log" in tables


def test_head_does_not_have_legacy_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    tables = _tables(test_db_url)
    assert "processed_files" not in tables
    assert "sync_state" not in tables


# ── migration 003 state ───────────────────────────────────────────────────────

def test_migration_003_creates_opensearch_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "003")
    tables = _tables(test_db_url)
    assert "files" in tables
    assert "chunks" in tables
    assert "translation_settings" in tables
    assert "search_query_log" in tables
    assert "processed_files" in tables
    assert "sync_state" in tables


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
    command.downgrade(alembic_cfg, "003")
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM translation_settings")).scalar()
    engine.dispose()
    assert count == 1


# ── downgrade behavior ────────────────────────────────────────────────────────

def test_downgrade_004_restores_legacy_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "003")
    tables = _tables(test_db_url)
    assert "processed_files" in tables
    assert "sync_state" in tables
    assert "files" in tables  # 003 tables still present


def test_downgrade_003_removes_opensearch_tables(alembic_cfg, test_db_url):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "002")
    tables = _tables(test_db_url)
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
    tables = _tables(test_db_url)
    assert "files" in tables
    assert "chunks" in tables
    assert "users" in tables
    assert "watched_folders" in tables
    assert "processed_files" not in tables
    assert "sync_state" not in tables
