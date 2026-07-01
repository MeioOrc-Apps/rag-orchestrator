import logging
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

def _read_version() -> str:
    toml = Path(__file__).parent.parent / "pyproject.toml"
    with toml.open("rb") as f:
        return tomllib.load(f)["project"]["version"]
from fastapi.responses import FileResponse, Response

from app.routers import admin as admin_router
from app.routers import files as files_router
from app.routers import folders as folders_router
from app.routers import search as search_router
from app.routers import sync as sync_router
from app.scheduler import add_interval_job, create_scheduler

_STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import Settings
    from app.jobs.delete_job import run_delete_job
    from app.jobs.index_job import run_index_job
    from app.jobs.parse_job import run_parse_job
    from app.jobs.translate_job import run_translate_job
    from app.routers.sync import run_sync_job

    settings = Settings()
    scheduler = create_scheduler()
    add_interval_job(scheduler, run_sync_job, settings.scan_interval_minutes, "scan")
    add_interval_job(scheduler, run_parse_job, settings.parse_interval_minutes, "parse")
    add_interval_job(scheduler, run_translate_job, settings.translate_interval_minutes, "translate")
    add_interval_job(scheduler, run_index_job, settings.index_interval_minutes, "index")
    add_interval_job(scheduler, run_delete_job, settings.index_interval_minutes, "delete")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="RAG Orchestrator", version=_read_version(), lifespan=lifespan)
app.include_router(folders_router.router)
app.include_router(sync_router.router)
app.include_router(files_router.router)
app.include_router(search_router.router)
app.include_router(admin_router.router)


@app.get("/{full_path:path}", include_in_schema=False)
async def _spa_fallback(full_path: str) -> Response:
    candidate = _STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(status_code=404)
