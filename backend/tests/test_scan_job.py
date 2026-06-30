"""Integration tests for scan_job."""
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def folder_and_source(db_session, tmp_path):
    from app.models import User, WatchedFolder
    user = db_session.query(User).filter(User.username == "sergio").first()
    source = tmp_path / "source"
    source.mkdir()
    folder = WatchedFolder(
        owner_id=user.id,
        host_path=str(source),
        dest_subdir="docs",
        recursive=True,
        enabled=True,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)
    return folder, source


class TestNewFileInserted:
    def test_new_file_inserted_with_pending_status_and_correct_domain(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File

        folder, source = folder_and_source
        (source / "note.md").write_text("hello world")

        result = run_scan(db_session, [folder])

        assert result["inserted"] == 1
        f = db_session.query(File).first()
        assert f.parse_status == "pending"
        assert f.domain == "docs"
        assert f.filename == "note.md"
        assert f.path == str(source / "note.md")

    def test_new_file_records_hash_and_size(self, db_session, folder_and_source):
        from app.jobs.scan_job import run_scan
        from app.models import File
        from app.pipeline.scanner import compute_hash

        folder, source = folder_and_source
        filepath = source / "note.md"
        filepath.write_text("hello world")

        run_scan(db_session, [folder])

        f = db_session.query(File).first()
        assert f.file_hash == compute_hash(filepath)
        assert f.file_size_bytes == filepath.stat().st_size


class TestUnchangedFileSkipped:
    def test_unchanged_file_is_skipped_on_second_scan(self, db_session, folder_and_source):
        from app.jobs.scan_job import run_scan
        from app.models import File

        folder, source = folder_and_source
        (source / "note.md").write_text("hello")

        run_scan(db_session, [folder])
        result = run_scan(db_session, [folder])

        assert result["skipped"] == 1
        assert result["inserted"] == 0
        assert db_session.query(File).count() == 1


class TestModifiedFileUpdated:
    def test_modified_file_resets_parse_status_and_updates_hash(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File

        folder, source = folder_and_source
        f = source / "note.md"
        f.write_text("original")

        run_scan(db_session, [folder])
        file_row = db_session.query(File).first()
        old_hash = file_row.file_hash

        f.write_text("modified content that is completely different")
        result = run_scan(db_session, [folder])

        assert result["updated"] == 1
        db_session.refresh(file_row)
        assert file_row.parse_status == "pending"
        assert file_row.file_hash != old_hash

    def test_modified_file_marks_indexed_chunks_as_deleted(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File, Chunk

        folder, source = folder_and_source
        f = source / "note.md"
        f.write_text("original")

        run_scan(db_session, [folder])
        file_row = db_session.query(File).first()

        chunk = Chunk(
            file_id=file_row.id,
            chunk_index=0,
            content_original="original",
            source_language="en",
            char_count=8,
            index_status="done",
            opensearch_id="os-1",
        )
        db_session.add(chunk)
        db_session.commit()

        f.write_text("completely different content here now")
        run_scan(db_session, [folder])

        db_session.refresh(chunk)
        assert chunk.index_status == "deleted"


class TestDeletedFileSoftDeleted:
    def test_file_removed_from_disk_gets_deleted_at_set(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File

        folder, source = folder_and_source
        f = source / "note.md"
        f.write_text("hello")

        run_scan(db_session, [folder])
        file_row = db_session.query(File).first()
        assert file_row.deleted_at is None

        f.unlink()
        result = run_scan(db_session, [folder])

        assert result["deleted"] == 1
        db_session.refresh(file_row)
        assert file_row.deleted_at is not None

    def test_deleted_file_chunks_marked_as_deleted(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File, Chunk

        folder, source = folder_and_source
        f = source / "note.md"
        f.write_text("hello")

        run_scan(db_session, [folder])
        file_row = db_session.query(File).first()

        chunk = Chunk(
            file_id=file_row.id,
            chunk_index=0,
            content_original="hello",
            source_language="en",
            char_count=5,
            index_status="done",
            opensearch_id="os-1",
        )
        db_session.add(chunk)
        db_session.commit()

        f.unlink()
        run_scan(db_session, [folder])

        db_session.refresh(chunk)
        assert chunk.index_status == "deleted"

    def test_soft_deleted_file_not_re_deleted_on_next_scan(
        self, db_session, folder_and_source
    ):
        from app.jobs.scan_job import run_scan
        from app.models import File

        folder, source = folder_and_source
        f = source / "note.md"
        f.write_text("hello")

        run_scan(db_session, [folder])
        f.unlink()
        run_scan(db_session, [folder])  # soft-delete

        result = run_scan(db_session, [folder])  # no file on disk, already soft-deleted
        assert result["deleted"] == 0
        assert result["inserted"] == 0
        assert db_session.query(File).count() == 1


class TestDisabledFolder:
    def test_disabled_folder_is_not_scanned(self, db_session, tmp_path):
        from app.jobs.scan_job import run_scan
        from app.models import User, WatchedFolder, File

        user = db_session.query(User).filter(User.username == "sergio").first()
        source = tmp_path / "src2"
        source.mkdir()
        (source / "file.md").write_text("content")

        folder = WatchedFolder(
            owner_id=user.id,
            host_path=str(source),
            dest_subdir="docs",
            recursive=True,
            enabled=False,
        )
        db_session.add(folder)
        db_session.commit()

        result = run_scan(db_session, [folder])

        assert result["inserted"] == 0
        assert db_session.query(File).count() == 0
