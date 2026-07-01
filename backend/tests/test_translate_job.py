"""Integration tests for translate_job."""
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.integration


@pytest.fixture
def translation_enabled(db_session):
    """Enable translation in DB settings (disabled by default in migration seed)."""
    from app.models import TranslationSettings
    ts = db_session.query(TranslationSettings).first()
    if ts:
        ts.model = "local:test-model"
        ts.enabled = True
        db_session.commit()


def _make_pt_chunk(db_session, tmp_path, name="doc.md", text="Olá mundo"):
    from app.models import User, File, Chunk
    from app.pipeline.scanner import compute_hash

    fpath = tmp_path / name
    fpath.write_text(text)
    file_row = File(
        path=str(fpath), filename=name, domain="docs",
        file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()
    chunk = Chunk(
        file_id=file_row.id, chunk_index=0,
        content_original=text, source_language="pt",
        char_count=len(text), translation_status="pending",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


def _make_en_chunk(db_session, tmp_path, name="en.md", text="Hello world"):
    from app.models import File, Chunk
    from app.pipeline.scanner import compute_hash

    fpath = tmp_path / name
    fpath.write_text(text)
    file_row = File(
        path=str(fpath), filename=name, domain="docs",
        file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()
    chunk = Chunk(
        file_id=file_row.id, chunk_index=0,
        content_original=text, source_language="en",
        char_count=len(text), translation_status="pending",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


@pytest.fixture
def pending_pt_chunk(db_session, tmp_path):
    return _make_pt_chunk(db_session, tmp_path)


@pytest.fixture
def pending_en_chunk(db_session, tmp_path):
    return _make_en_chunk(db_session, tmp_path)


# ── PT→EN translation ────────────────────────────────────────────────────────

@pytest.mark.usefixtures("translation_enabled")
class TestTranslatePTtoEN:
    def test_pt_chunk_gets_content_en_set(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Hello world"
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.content_en == "Hello world"
        assert pending_pt_chunk.content_pt == "Olá mundo"

    def test_pt_chunk_status_set_to_done(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Hello"
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.translation_status == "done"

    def test_pt_chunk_records_model(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Hello"
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.translation_model is not None

    def test_pt_chunk_translated_at_set(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Hello"
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.translated_at is not None


# ── EN→PT translation ────────────────────────────────────────────────────────

@pytest.mark.usefixtures("translation_enabled")
class TestTranslateENtoPT:
    def test_en_chunk_gets_content_pt_set(self, db_session, pending_en_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Olá mundo"
            run_translate(db_session)

        db_session.refresh(pending_en_chunk)
        assert pending_en_chunk.content_pt == "Olá mundo"
        assert pending_en_chunk.content_en == "Hello world"

    def test_en_chunk_status_set_to_done(self, db_session, pending_en_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Olá"
            run_translate(db_session)

        db_session.refresh(pending_en_chunk)
        assert pending_en_chunk.translation_status == "done"

    def test_en_chunk_uses_pt_prompt(self, db_session, pending_en_chunk):
        from app.jobs.translate_job import run_translate

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.return_value = "Olá"
            run_translate(db_session)

        call_kwargs = MockLLM.return_value.translate.call_args
        assert "Portuguese" in str(call_kwargs)


# ── No model (disabled) ───────────────────────────────────────────────────────

class TestTranslateDisabled:
    def test_pt_chunk_no_model_copies_original_to_content_pt(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate

        chunk = _make_pt_chunk(db_session, tmp_path, text="Olá mundo")

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            MockLLM.assert_not_called()

        db_session.refresh(chunk)
        assert chunk.content_pt == "Olá mundo"
        assert chunk.content_en == ""
        assert chunk.translation_status == "done"

    def test_en_chunk_no_model_copies_original_to_content_en(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate

        chunk = _make_en_chunk(db_session, tmp_path, text="Hello world")

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            MockLLM.assert_not_called()

        db_session.refresh(chunk)
        assert chunk.content_en == "Hello world"
        assert chunk.content_pt == ""
        assert chunk.translation_status == "done"


# ── Retry ─────────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("translation_enabled")
class TestTranslateJobRetry:
    def test_failed_translation_retries_up_to_max(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.side_effect = LLMError("timeout")
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.translation_status == "failed"
        assert pending_pt_chunk.translation_error is not None

    def test_retry_succeeds_on_second_attempt(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.side_effect = [LLMError("first fail"), "Hello world"]
            run_translate(db_session)

        db_session.refresh(pending_pt_chunk)
        assert pending_pt_chunk.translation_status == "done"
        assert pending_pt_chunk.content_en == "Hello world"

    def test_translate_retries_exact_max_times_before_failing(self, db_session, pending_pt_chunk):
        from app.jobs.translate_job import run_translate
        from app.llm_client import LLMError

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            MockLLM.return_value.translate.side_effect = LLMError("always fails")
            run_translate(db_session, max_retries=2)

        assert MockLLM.return_value.translate.call_count == 2


# ── Batching ──────────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("translation_enabled")
class TestTranslateJobBatching:
    def test_respects_batch_size_from_translation_settings(self, db_session, tmp_path):
        from app.jobs.translate_job import run_translate
        from app.models import File, Chunk, TranslationSettings
        from app.pipeline.scanner import compute_hash

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
            MockLLM.return_value.translate.return_value = "translated"
            result = run_translate(db_session)

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
            char_count=12, translation_status="done",
            content_en="already done", content_pt="já feito",
        )
        db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.translate_job.LLMClient") as MockLLM:
            run_translate(db_session)
            MockLLM.return_value.translate.assert_not_called()
