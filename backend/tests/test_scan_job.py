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
