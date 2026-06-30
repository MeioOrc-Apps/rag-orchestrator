import uuid

from sqlalchemy.orm import Session

from app.models import WatchedFolder
from app.schemas.folders import FolderCreate, FolderUpdate


def list_folders(session: Session, owner_id: uuid.UUID) -> list[WatchedFolder]:
    return session.query(WatchedFolder).filter(WatchedFolder.owner_id == owner_id).all()


def get_folder(session: Session, folder_id: uuid.UUID, owner_id: uuid.UUID) -> WatchedFolder | None:
    return (
        session.query(WatchedFolder)
        .filter(WatchedFolder.id == folder_id, WatchedFolder.owner_id == owner_id)
        .first()
    )


def create_folder(session: Session, owner_id: uuid.UUID, data: FolderCreate) -> WatchedFolder:
    folder = WatchedFolder(
        owner_id=owner_id,
        host_path=data.host_path,
        dest_subdir=data.dest_subdir,
        recursive=data.recursive,
        enabled=data.enabled,
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


def update_folder(
    session: Session, folder_id: uuid.UUID, owner_id: uuid.UUID, data: FolderUpdate
) -> WatchedFolder | None:
    folder = get_folder(session, folder_id, owner_id)
    if folder is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(folder, field, value)
    session.commit()
    session.refresh(folder)
    return folder


def delete_folder(session: Session, folder_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    folder = get_folder(session, folder_id, owner_id)
    if folder is None:
        return False
    session.delete(folder)
    session.commit()
    return True
