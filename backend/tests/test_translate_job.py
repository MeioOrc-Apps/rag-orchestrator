"""Integration tests for translate_job."""
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.integration


@pytest.fixture
def pending_chunk(db_session, tmp_path):
    """Insert a File + one pending Chunk into db_session."""
    from app.models import User, File, Chunk
    from app.pipeline.scanner import compute_hash

    user = db_session.query(User).filter(User.username == "sergio").first()
    fpath = tmp_path / "doc.md"
    fpath.write_text("Olá mundo")

    file_row = File(
        path=str(fpath),
        filename="doc.md",
        domain="docs",
        file_hash=compute_hash(fpath),
        file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()

    chunk = Chunk(
        file_id=file_row.id,
        chunk_index=0,
        content_original="Olá mundo",
        source_language="pt",
        char_count=9,
        translation_status="pending",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


class TestTranslateJobSuccess:
    def test_pending_chunk_gets_content_en_set(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.return_value = "Hello world"
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.content_en == "Hello world"

    def test_pending_chunk_status_set_to_done(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.return_value = "Hello world"
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.translation_status == "done"

    def test_pending_chunk_records_translation_model(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.return_value = "Hello"
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.translation_model is not None

    def test_pending_chunk_translated_at_set(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.return_value = "Hello"
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.translated_at is not None


class TestTranslateJobNotNeeded:
    def test_not_needed_chunk_copies_original_to_content_en(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "en.md"
        fpath.write_text("Hello world")
        file_row = File(
            path=str(fpath),
            filename="en.md",
            domain="docs",
            file_hash=compute_hash(fpath),
            file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()

        chunk = Chunk(
            file_id=file_row.id,
            chunk_index=0,
            content_original="Hello world",
            source_language="en",
            char_count=11,
            translation_status="not_needed",
        )
        db_session.add(chunk)
        db_session.commit()
        db_session.refresh(chunk)

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            MockLLM.assert_not_called()

        db_session.refresh(chunk)
        assert chunk.content_en == "Hello world"
        assert chunk.translation_status == "done"

    def test_not_needed_chunk_no_llm_call(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "en2.md"
        fpath.write_text("English text here")
        file_row = File(
            path=str(fpath), filename="en2.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()
        chunk = Chunk(
            file_id=file_row.id, chunk_index=0, content_original="English text here",
            source_language="en", char_count=17, translation_status="not_needed",
        )
        db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            instance = MockLLM.return_value
            instance.translate.assert_not_called()


class TestTranslateJobRetry:
    def test_failed_translation_retries_up_to_max(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.side_effect = LLMError("timeout")
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.translation_status == "failed"
        assert pending_chunk.translation_error is not None

    def test_retry_succeeds_on_second_attempt(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.side_effect = [LLMError("first fail"), "Hello world"]
            run_translate(db_session)

        db_session.refresh(pending_chunk)
        assert pending_chunk.translation_status == "done"
        assert pending_chunk.content_en == "Hello world"

    def test_translate_retries_exact_max_times_before_failing(self, db_session, pending_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.side_effect = LLMError("always fails")
            run_translate(db_session, max_retries=2)

        assert instance.translate.call_count == 2


class TestTranslateJobBatching:
    def test_respects_batch_size_from_translation_settings(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate
        from app.models import File, Chunk, TranslationSettings
        from app.pipeline.scanner import compute_hash

        # Update batch_size to 1
        settings_row = db_session.query(TranslationSettings).first()
        settings_row.batch_size = 1
        db_session.commit()

        fpath = tmp_path / "multi.md"
        fpath.write_text("text")
        file_row = File(
            path=str(fpath), filename="multi.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()

        for i in range(3):
            db_session.add(Chunk(
                file_id=file_row.id, chunk_index=i,
                content_original=f"chunk {i}", source_language="pt",
                char_count=7, translation_status="pending",
            ))
        db_session.commit()

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            instance = MockLLM.return_value
            instance.translate.return_value = "translated"
            result = run_translate(db_session)

        # batch_size=1 means only 1 chunk processed per run
        assert result["translated"] == 1

    def test_already_done_chunks_are_skipped(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "done.md"
        fpath.write_text("text")
        file_row = File(
            path=str(fpath), filename="done.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()
        chunk = Chunk(
            file_id=file_row.id, chunk_index=0,
            content_original="already done", source_language="en",
            char_count=12, translation_status="done", content_en="already done",
        )
        db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            MockLLM.return_value.translate.assert_not_called()
