from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import folders as folders_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="RAG Orchestrator", version="0.1.0", lifespan=lifespan)
app.include_router(folders_router.router)
