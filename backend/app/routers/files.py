from fastapi import APIRouter
from app.schemas.files import PaginatedResponse, FileResponse

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=PaginatedResponse[FileResponse])
def list_files():
    return PaginatedResponse(items=[], total=0, limit=50, offset=0)
