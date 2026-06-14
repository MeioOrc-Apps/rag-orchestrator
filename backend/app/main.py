from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response

from app.routers import files as files_router
from app.routers import folders as folders_router
from app.routers import sync as sync_router
from app.scheduler import create_and_configure_scheduler

_STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import Settings
    from app.routers.sync import run_sync_job

    settings = Settings()
    scheduler = create_and_configure_scheduler(
        interval_minutes=settings.scan_interval_minutes,
        job_func=run_sync_job,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="RAG Orchestrator", version="0.1.0", lifespan=lifespan)
app.include_router(folders_router.router)
app.include_router(sync_router.router)
app.include_router(files_router.router)


@app.get("/{full_path:path}", include_in_schema=False)
async def _spa_fallback(full_path: str) -> Response:
    candidate = _STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(status_code=404)
