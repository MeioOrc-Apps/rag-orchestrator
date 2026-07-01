"""Integration tests for index_job — real DB, mocked OpenSearchClient."""
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.integration


@pytest.fixture
def indexable_chunk(db_session, tmp_path):
    """File + Chunk ready to index (translation done)."""
    from app.models import File, Chunk
    from app.pipeline.scanner import compute_hash

    fpath = tmp_path / "doc.md"
    fpath.write_text("Hello world")
    file_row = File(
        path=str(fpath), filename="doc.md", domain="docs",
        file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
        parse_status="done",
    )
    db_session.add(file_row)
    db_session.flush()

    chunk = Chunk(
        file_id=file_row.id, chunk_index=0,
        content_original="Hello world", source_language="en",
        content_en="Hello world",
        char_count=11,
        translation_status="done",
        index_status="pending",
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk, file_row


class TestIndexJobSuccess:
    def test_indexable_chunk_gets_index_status_done(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([(str(chunk.id), "os-id-1")], [])
            run_index(db_session)

        db_session.refresh(chunk)
        assert chunk.index_status == "done"

    def test_indexable_chunk_gets_opensearch_id(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([(str(chunk.id), "os-abc-123")], [])
            run_index(db_session)

        db_session.refresh(chunk)
        assert chunk.opensearch_id == "os-abc-123"

    def test_indexable_chunk_gets_indexed_at(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([(str(chunk.id), "os-1")], [])
            run_index(db_session)

        db_session.refresh(chunk)
        assert chunk.indexed_at is not None

    def test_ensure_index_called_per_domain(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([(str(chunk.id), "os-1")], [])
            run_index(db_session)

        instance.ensure_index.assert_called_once_with("docs")

    def test_doc_sent_to_bulk_index_contains_content_en(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([(str(chunk.id), "os-1")], [])
            run_index(db_session)

        call_args = instance.bulk_index.call_args
        domain_arg, docs_arg = call_args[0]
        assert domain_arg == "docs"
        assert len(docs_arg) == 1
        assert docs_arg[0]["content_en"] == "Hello world"
        assert docs_arg[0]["chunk_id"] == str(chunk.id)


class TestIndexJobPartialFailure:
    def test_failed_chunk_marked_as_failed(self, db_session, indexable_chunk):
        from app.jobs.index_job import run_index

        chunk, _ = indexable_chunk
        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = ([], [(str(chunk.id), "mapping error")])
            run_index(db_session)

        db_session.refresh(chunk)
        assert chunk.index_status == "failed"
        assert chunk.index_error == "mapping error"

    def test_partial_batch_commits_successes_despite_failures(self, db_session, tmp_path):
        from app.jobs.index_job import run_index
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "multi.md"
        fpath.write_text("text")
        file_row = File(
            path=str(fpath), filename="multi.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()

        c1 = Chunk(
            file_id=file_row.id, chunk_index=0,
            content_original="chunk one", source_language="en", content_en="chunk one",
            char_count=9, translation_status="done", index_status="pending",
        )
        c2 = Chunk(
            file_id=file_row.id, chunk_index=1,
            content_original="chunk two", source_language="en", content_en="chunk two",
            char_count=9, translation_status="done", index_status="pending",
        )
        db_session.add_all([c1, c2])
        db_session.commit()
        db_session.refresh(c1)
        db_session.refresh(c2)

        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            instance = MockOS.return_value
            instance.ensure_index.return_value = True
            instance.bulk_index.return_value = (
                [(str(c1.id), "os-1")],
                [(str(c2.id), "bad mapping")],
            )
            result = run_index(db_session)

        db_session.refresh(c1)
        db_session.refresh(c2)
        assert c1.index_status == "done"
        assert c2.index_status == "failed"
        assert result["indexed"] == 1
        assert result["failed"] == 1


class TestIndexJobSkipsNotReady:
    def test_pending_translation_chunk_not_indexed(self, db_session, tmp_path):
        from app.jobs.index_job import run_index
        from app.models import File, Chunk
        from app.pipeline.scanner import compute_hash

        fpath = tmp_path / "notready.md"
        fpath.write_text("text")
        file_row = File(
            path=str(fpath), filename="notready.md", domain="docs",
            file_hash=compute_hash(fpath), file_size_bytes=fpath.stat().st_size,
            parse_status="done",
        )
        db_session.add(file_row)
        db_session.flush()
        chunk = Chunk(
            file_id=file_row.id, chunk_index=0,
            content_original="not yet", source_language="pt",
            char_count=7, translation_status="pending", index_status="pending",
        )
        db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            run_index(db_session)
            MockOS.return_value.bulk_index.assert_not_called()

    def test_already_indexed_chunk_not_re_indexed(self, db_session, tmp_path):
        from app.jobs.index_job import run_index
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
            content_original="already indexed", source_language="en", content_en="already indexed",
            char_count=15, translation_status="done", index_status="done",
            opensearch_id="existing-os-id",
        )
        db_session.add(chunk)
        db_session.commit()

        with patch("app.jobs.index_job.OpenSearchClient") as MockOS:
            run_index(db_session)
            MockOS.return_value.bulk_index.assert_not_called()
