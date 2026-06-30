import uuid
import pytest
from datetime import datetime, timezone

pytestmark = pytest.mark.integration


def test_file_model_persists_and_retrieves(db_session):
    from app.models import File

    f = File(
        path="/inputs/rpg/manual.md",
        filename="manual.md",
        domain="rpg",
        file_hash="abc123",
        file_size_bytes=1024,
        mime_type="text/markdown",
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)

    assert f.id is not None
    assert f.path == "/inputs/rpg/manual.md"
    assert f.domain == "rpg"
    assert f.parse_status == "pending"
    assert f.deleted_at is None
    assert f.created_at is not None


def test_file_model_path_is_unique(db_session):
    from app.models import File
    from sqlalchemy.exc import IntegrityError

    f1 = File(path="/inputs/a.md", filename="a.md", domain="x", file_hash="h1", file_size_bytes=10)
    f2 = File(path="/inputs/a.md", filename="a.md", domain="x", file_hash="h2", file_size_bytes=10)
    db_session.add(f1)
    db_session.commit()
    db_session.add(f2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_chunk_model_persists_and_retrieves(db_session):
    from app.models import File, Chunk

    f = File(path="/inputs/rpg/a.md", filename="a.md", domain="rpg", file_hash="h1", file_size_bytes=100)
    db_session.add(f)
    db_session.commit()

    c = Chunk(
        file_id=f.id,
        chunk_index=0,
        content_original="Hello world this is a chunk of text",
        source_language="en",
        char_count=35,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    assert c.id is not None
    assert c.file_id == f.id
    assert c.chunk_index == 0
    assert c.translation_status == "pending"
    assert c.index_status == "pending"
    assert c.content_en is None
    assert c.opensearch_id is None


def test_chunk_file_chunk_index_unique(db_session):
    from app.models import File, Chunk
    from sqlalchemy.exc import IntegrityError

    f = File(path="/inputs/b.md", filename="b.md", domain="x", file_hash="h2", file_size_bytes=50)
    db_session.add(f)
    db_session.commit()

    c1 = Chunk(file_id=f.id, chunk_index=0, content_original="text", source_language="en", char_count=4)
    c2 = Chunk(file_id=f.id, chunk_index=0, content_original="other", source_language="en", char_count=5)
    db_session.add(c1)
    db_session.commit()
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_chunk_cascades_on_file_delete(db_session):
    from app.models import File, Chunk

    f = File(path="/inputs/c.md", filename="c.md", domain="x", file_hash="h3", file_size_bytes=50)
    db_session.add(f)
    db_session.commit()

    c = Chunk(file_id=f.id, chunk_index=0, content_original="x", source_language="pt", char_count=1)
    db_session.add(c)
    db_session.commit()

    db_session.delete(f)
    db_session.commit()

    remaining = db_session.query(Chunk).filter(Chunk.file_id == f.id).all()
    assert remaining == []


def test_translation_settings_persists(db_session):
    from app.models import TranslationSettings

    ts = TranslationSettings(
        model="local:qwen2.5:7b",
        prompt_template="Translate: {text}",
        target_language="en",
        batch_size=5,
        enabled=True,
    )
    db_session.add(ts)
    db_session.commit()
    db_session.refresh(ts)

    assert ts.id is not None
    assert ts.model == "local:qwen2.5:7b"
    assert ts.enabled is True


def test_search_query_log_persists(db_session):
    from app.models import SearchQueryLog

    log = SearchQueryLog(
        query_original="esquiva",
        query_enriched="esquiva evasão dodge evasion",
        domain_filter="rpg",
        results_count=5,
        top_score=1.42,
        latency_ms=38,
        enrichment_used=True,
        fallback_used=False,
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    assert log.id is not None
    assert log.query_original == "esquiva"
    assert log.enrichment_used is True
    assert log.created_at is not None


def test_user_and_watched_folder_still_exist(db_session):
    from app.models import User, WatchedFolder
    assert User.__tablename__ == "users"
    assert WatchedFolder.__tablename__ == "watched_folders"
