import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import folders as folders_crud
from app.dependencies import get_db
from app.models import User
from app.schemas.folders import FolderCreate, FolderResponse, FolderUpdate

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _default_owner(db: Session) -> User:
    from app.config import Settings
    username = Settings().default_owner_username
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=500, detail="Default owner not seeded in database")
    return user


@router.get("", response_model=list[FolderResponse])
def list_folders(db: Session = Depends(get_db)):
    owner = _default_owner(db)
    return folders_crud.list_folders(db, owner_id=owner.id)


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(data: FolderCreate, db: Session = Depends(get_db)):
    owner = _default_owner(db)
    return folders_crud.create_folder(db, owner_id=owner.id, data=data)


@router.get("/{folder_id}", response_model=FolderResponse)
def get_folder(folder_id: uuid.UUID, db: Session = Depends(get_db)):
    owner = _default_owner(db)
    folder = folders_crud.get_folder(db, folder_id=folder_id, owner_id=owner.id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.patch("/{folder_id}", response_model=FolderResponse)
def update_folder(folder_id: uuid.UUID, data: FolderUpdate, db: Session = Depends(get_db)):
    owner = _default_owner(db)
    folder = folders_crud.update_folder(db, folder_id=folder_id, owner_id=owner.id, data=data)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: uuid.UUID, db: Session = Depends(get_db)):
    owner = _default_owner(db)
    deleted = folders_crud.delete_folder(db, folder_id=folder_id, owner_id=owner.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Folder not found")
