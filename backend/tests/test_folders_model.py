import pytest
from app.models import WatchedFolder, User


pytestmark = pytest.mark.integration


def test_watched_folder_persists_with_owner_id(db_session):
    owner = db_session.query(User).filter(User.username == "sergio").first()
    assert owner is not None

    folder = WatchedFolder(
        owner_id=owner.id,
        host_path="/tmp/docs",
        dest_subdir="docs",
    )
    db_session.add(folder)
    db_session.commit()

    retrieved = db_session.query(WatchedFolder).filter(WatchedFolder.id == folder.id).first()
    assert retrieved is not None
    assert retrieved.owner_id == owner.id
    assert retrieved.host_path == "/tmp/docs"
    assert retrieved.dest_subdir == "docs"
    assert retrieved.recursive is True
    assert retrieved.enabled is True
    assert retrieved.created_at is not None


def test_watched_folder_accessible_via_owner_relationship(db_session):
    owner = db_session.query(User).filter(User.username == "sergio").first()

    folder = WatchedFolder(
        owner_id=owner.id,
        host_path="/tmp/books",
        dest_subdir="books",
        recursive=False,
        enabled=False,
    )
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)

    assert folder.owner.username == "sergio"
    assert folder.recursive is False
    assert folder.enabled is False
