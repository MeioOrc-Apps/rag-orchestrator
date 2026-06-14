# RAG Orchestrator

Automated document ingestion pipeline for [LightRAG](https://github.com/HKUDS/LightRAG).

Watches configured host folders on a schedule (default: every 30 minutes) or on demand. Detects new and changed files by content hash, converts documents (PDF, DOCX, images, …) to Markdown via [Docling](https://github.com/DS4SD/docling), writes the result directly into LightRAG's input directory, and triggers a scan — so your knowledge base stays up to date automatically.

## How it works

```
Watched folder(s)
      │
      ▼
  scan + SHA-256 dedup
      │
      ├─ .md / .txt / .markdown ──────────────► copy as-is
      │
      └─ .pdf / .docx / .pptx / images / … ──► Docling → Markdown
                                                      │
                                              LightRAG input dir
                                                      │
                                              POST /documents/scan
```

Files already processed with the same content hash are skipped — rescanning is safe and cheap.

## Features

- **Folder management** — add/edit/remove watched folders via web UI or API
- **Content deduplication** — SHA-256 per file; same hash → skip
- **Automatic scheduling** — APScheduler runs the pipeline at a configurable interval
- **Manual trigger** — "Sync Now" button or `POST /api/sync`
- **Per-file status tracking** — `done`, `failed`, `skipped`, `processing` with error messages
- **React web UI** — Status / Folders / Files tabs served from the same container

## Prerequisites

| Dependency | Purpose | Notes |
|---|---|---|
| Python 3.12 | Backend runtime | `python3.12 --version` |
| Node.js 22 | Frontend build | `node --version` |
| Docker | PostgreSQL for development/tests | Only needed for the DB |
| LightRAG | Document indexing target | Must be reachable from the orchestrator |
| Docling Serve | PDF/DOCX/image conversion | Optional — only for non-Markdown files |

### Install Python 3.12 (macOS)

```bash
brew install python@3.12
```

### Install Node.js 22 (macOS)

```bash
brew install node@22
```

## Local development — step by step

### 1. Clone and enter the repo

```bash
git clone <repo-url> rag-orchestrator
cd rag-orchestrator
```

### 2. Start a PostgreSQL instance for development

```bash
docker run -d \
  --name rag-postgres \
  -e POSTGRES_USER=orchestrator \
  -e POSTGRES_PASSWORD=orchestrator \
  -e POSTGRES_DB=orchestrator \
  -p 5432:5432 \
  postgres:16-alpine
```

### 3. Set up the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create a `.env` file at the repo root (copy from the example):

```bash
cd ..
cp .env.example .env
```

Edit `.env` with your values:

```env
DATABASE_URL=postgresql+psycopg://orchestrator:orchestrator@localhost:5432/orchestrator
DOCLING_BASE_URL=http://localhost:5001          # Docling Serve address
LIGHTRAG_BASE_URL=http://localhost:9621         # LightRAG address
LIGHTRAG_USERNAME=admin
LIGHTRAG_PASSWORD=admin123
LIGHTRAG_INPUT_DIR=/path/to/lightrag/inputs    # shared folder with LightRAG
DEFAULT_OWNER_USERNAME=default
SCAN_INTERVAL_MINUTES=30
```

### 4. Run database migrations and seed

```bash
cd backend
source .venv/bin/activate

# Apply migrations (creates tables)
alembic upgrade head

# Seed the default user
python -c "
from app.config import Settings
from app.database import get_engine, get_session_factory
from app.seed import seed_from_config
s = Settings()
engine = get_engine(s.database_url)
session = get_session_factory(engine)()
seed_from_config(session)
session.close()
engine.dispose()
print('Seeded.')
"
```

### 5. Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 6. Start the frontend (development mode)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend at `http://localhost:5173` — API calls are proxied to `:8000` via Vite's proxy config.

## Running tests

### Backend tests

Requires a running PostgreSQL. Tests default to `localhost:5433` (separate test container); set `DATABASE_URL` to point to any reachable instance:

```bash
# Start a dedicated test DB (avoids touching dev data)
docker run -d \
  --name rag-test-postgres \
  -e POSTGRES_USER=orchestrator \
  -e POSTGRES_PASSWORD=orchestrator \
  -e POSTGRES_DB=orchestrator \
  -p 5433:5432 \
  postgres:16-alpine

cd backend
source .venv/bin/activate
pytest tests/ -q
```

To run only unit tests (no database required):

```bash
pytest tests/ -q -m "not integration"
```

### Frontend tests

```bash
cd frontend
npm test -- --run
```

### Full suite

```bash
# from backend/
pytest tests/ -q
# from frontend/
npm test -- --run
```

Expected: **107 backend + 18 frontend = 125 tests, all green**.

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/folders` | List watched folders |
| `POST` | `/api/folders` | Add a folder (`host_path`, `dest_subdir`, `recursive`, `enabled`) |
| `GET` | `/api/folders/{id}` | Get folder detail |
| `PATCH` | `/api/folders/{id}` | Update folder fields |
| `DELETE` | `/api/folders/{id}` | Remove a folder |
| `POST` | `/api/sync` | Trigger sync pipeline immediately |
| `GET` | `/api/sync/status` | Last sync result |
| `GET` | `/api/files` | List processed files (filter: `?status=done\|failed\|skipped\|processing`, `?folder_id=…`) |

Full OpenAPI schema: `GET /openapi.json` or `/docs` when the server is running.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | PostgreSQL connection string (`postgresql+psycopg://…`) |
| `DOCLING_BASE_URL` | yes | — | Docling Serve base URL |
| `LIGHTRAG_BASE_URL` | yes | — | LightRAG base URL |
| `LIGHTRAG_USERNAME` | yes | — | LightRAG login username |
| `LIGHTRAG_PASSWORD` | yes | — | LightRAG login password |
| `LIGHTRAG_INPUT_DIR` | yes | — | Path inside the container where LightRAG reads inputs |
| `DEFAULT_OWNER_USERNAME` | yes | — | Username of the seed user (e.g. `default`) |
| `SCAN_INTERVAL_MINUTES` | no | `30` | How often the scheduler runs the pipeline |

## Production deployment

### Docker Compose (single server)

```bash
# Copy and edit the environment section in docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d
```

The `app` service:
- Runs migrations automatically on startup (`alembic upgrade head`)
- Serves the React frontend from the same port (`:8080`)
- Shares `/DATA/AppData/lightrag/inputs` with the LightRAG container

**Important:** the `LIGHTRAG_INPUT_DIR` volume must be the same physical directory that LightRAG mounts as its `INPUT_DIR`. The default mapping assumes LightRAG was installed from the CasaOS store with its default paths.

### CasaOS

Install via the community app store — the entry is in `Apps/RagOrchestrator/docker-compose.yml`.

Before starting:
1. Install LightRAG from the CasaOS store first
2. Set `LIGHTRAG_USERNAME` and `LIGHTRAG_PASSWORD` to match your LightRAG `AUTH_ACCOUNTS`
3. (Optional) Install DoclingServe for PDF/image conversion

### GitHub Actions / CI

The `.github/workflows/ci.yml` workflow:
1. Runs backend tests against a real PostgreSQL service container
2. Runs frontend tests with Vitest
3. On push to `main` (and only after both test jobs pass): builds a multi-arch Docker image (`linux/amd64`, `linux/arm64`) and pushes to `ghcr.io/<owner>/rag-orchestrator:latest`

## Project structure

```
rag-orchestrator/
├── backend/
│   ├── app/
│   │   ├── config.py          # pydantic-settings, all env vars
│   │   ├── database.py        # engine + session factory
│   │   ├── models.py          # User, WatchedFolder, ProcessedFile
│   │   ├── seed.py            # idempotent default user seed
│   │   ├── dependencies.py    # FastAPI DI (get_db)
│   │   ├── scheduler.py       # APScheduler setup
│   │   ├── lightrag_client.py # LightRAG HTTP client
│   │   ├── docling_client.py  # Docling HTTP client
│   │   ├── main.py            # FastAPI app + lifespan + SPA fallback
│   │   ├── pipeline/
│   │   │   ├── scanner.py     # compute_hash, scan
│   │   │   ├── router.py      # route by file extension
│   │   │   └── ingestor.py    # run_pipeline (dedup, copy/convert, record)
│   │   ├── routers/
│   │   │   ├── folders.py     # CRUD /api/folders
│   │   │   ├── sync.py        # POST /api/sync, GET /api/sync/status
│   │   │   └── files.py       # GET /api/files
│   │   ├── schemas/
│   │   │   ├── folders.py
│   │   │   └── files.py
│   │   └── crud/
│   │       └── folders.py
│   ├── alembic/
│   │   └── versions/001_initial.py
│   ├── tests/
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── api.ts
│       ├── App.tsx
│       └── components/
│           ├── FolderList.tsx
│           ├── StatusPage.tsx
│           └── FilesPage.tsx
├── Dockerfile
├── docker-compose.yml          # dev compose (postgres + backend placeholder)
├── docker-compose.prod.yml     # production
├── .env.example
├── .github/workflows/ci.yml
└── docs/
    ├── SPEC.md
    ├── PLAN.md
    └── PROGRESS.md
```

## Development workflow (Claude Code / TDD)

This project was built with strict TDD using Claude Code. See `CLAUDE.md` for the rules and `docs/PROGRESS.md` for the session-by-session build log.
