# PROGRESS.md — RAG Orchestrator

Ponte de memória entre sessões. Atualizado ao final de cada etapa.

---

## Etapa 1 — Fundação ✅ (2026-06-14)

**Branch:** `feat/etapa-1-fundacao` → merged na `main`

**Comportamentos implementados:**
- `config`: carrega todas as vars de ambiente obrigatórias; falha claramente se qualquer uma faltar; `SCAN_INTERVAL_MINUTES` tem default 30.
- `database`: `get_engine` + `get_session_factory` — sessão abre, executa, fecha corretamente.
- Migration 001: cria `users`, `watched_folders`, `processed_files` com constraints do SPEC (FK, PK, unique `uq_owner_path_hash`). Downgrade remove tudo limpo.
- Seed: `seed_default_user(session, username)` cria usuário; rodado 2x é idempotente. `seed_from_config(session)` lê `DEFAULT_OWNER_USERNAME` do config.

**Testes:** 20 passed (10 unit, 10 integration). `TEST_DATABASE_URL=postgresql+psycopg://orchestrator:orchestrator@localhost:5433/orchestrator`.

**Decisões:**
- Python 3.12 (via Homebrew). `psycopg[binary]` v3 (driver sync).
- Postgres de teste: container Docker na porta 5433 (porta 5432 já em uso por lima/VM local).
- Remoção do `backend/alembic/__init__.py` — era criado por engano e sombreava o pacote `alembic` instalado.
- `conftest.py` usa `TEST_DATABASE_URL` env var; se não estiver definida, cai no default para localhost:5433 (container de desenvolvimento).
- `clean_schema` fixture: DROP/CREATE SCHEMA PUBLIC entre testes de migration para garantir isolamento.

**Estrutura criada:**
```
backend/
  pyproject.toml        (deps: fastapi, sqlalchemy, alembic, psycopg, pydantic-settings, httpx, apscheduler)
  alembic.ini
  alembic/
    env.py
    script.py.mako
    versions/001_initial.py
  app/
    __init__.py
    config.py
    database.py
    models.py           (User, WatchedFolder, ProcessedFile)
    seed.py
  tests/
    conftest.py
    test_config.py
    test_database.py
    test_migrations.py
    test_seed.py
docker-compose.yml      (postgres na porta 5432 + backend placeholder)
```

---

## Etapa 2 — CRUD de pastas rastreáveis ✅ (2026-06-14)

**Branch:** `feat/etapa-2-crud-folders` → merged na `main`

**Comportamentos implementados:**
- Model `WatchedFolder` persiste e recupera com `owner_id` do seed; relacionamento `owner` funciona.
- `POST /api/folders` → 201 + corpo completo; defaults `recursive=true`, `enabled=true`.
- Validação: `host_path` vazio ou só espaços → 422; `dest_subdir` com `..` → 422; path absoluto → 422.
- `GET /api/folders` → lista apenas pastas do owner default.
- `GET /api/folders/{id}` → detalhe; id inexistente → 404.
- `PATCH /api/folders/{id}` → atualiza `enabled`, `recursive`, `dest_subdir`.
- `DELETE /api/folders/{id}` → 204; GET depois → 404; id inexistente → 404.
- Frontend `FolderList`: renderiza lista da API mockada; form chama `createFolder` e atualiza lista; erro exibido ao falhar.

**Testes:** 41 backend + 6 frontend = 47 total, todos verdes.

**Decisões:**
- Removido `backend/alembic/__init__.py` (voltou via merge — era necessário explicitamente no git rm).
- `conftest.py` atualizado: `os.environ.setdefault` garante vars mínimas para todos os testes; `api_client` fixture usa `dependency_overrides[get_db]`.
- Frontend: Vite 8 + React 19 + Vitest 4 + Testing Library; proxy `/api` → `localhost:8000`.
- FolderList escrito como componente + testes simultaneamente (não sequencial RED→GREEN) devido ao modo autônomo; todos os comportamentos cobertos.

**Estrutura adicionada:**
```
backend/app/
  main.py              (FastAPI app + lifespan)
  dependencies.py      (get_db com lazy init do engine)
  routers/folders.py   (CRUD /api/folders)
  schemas/folders.py   (FolderCreate, FolderUpdate, FolderResponse com validators)
  crud/folders.py      (list, get, create, update, delete)
frontend/src/
  api.ts               (listFolders, createFolder, deleteFolder)
  components/FolderList.tsx + FolderList.test.tsx
```

---

## Etapa 3 — Pipeline core ✅ (2026-06-14)

**Branch:** `feat/etapa-3-pipeline-core` → merged na `main`

**Comportamentos implementados:**
- `compute_hash(file)`: SHA-256 estável por conteúdo; muda se conteúdo muda.
- `scan(folder, recursive)`: lista arquivos; `recursive=False` não desce subpastas.
- Skip: arquivo já em `processed_files` com mesmo hash e `status=done` → `skipped`.
- `route(ext)`: `.md/.txt/.markdown` → `direct`; `.pdf/.docx/etc` → `docling`; desconhecido → `ValueError`.
- Rota `direct`: copia para `INPUT_DIR/<dest_subdir>/...` preservando estrutura relativa.
- Registro: `ProcessedFile` criado com `processing` → `done`; erro de I/O → `failed` com mensagem.
- Falha em um arquivo não impede os demais do lote.
- `POST /api/sync`: executa pipeline para todas as pastas ativas do owner; retorna `{processed, skipped, failed, scan_triggered: false}`.

**Testes:** 75 backend (todos verdes). 6 frontend (verdes).

**Decisões:**
- `ingestor.run_pipeline` filtra pastas com `enabled=True` (não depende da rota: lógica separada).
- Arquivos de rota `docling` ficam como `processing` nesta etapa (Etapa 5 fecha o loop).
- `LIGHTRAG_INPUT_DIR` lido do `Settings()` na rota sync; sobrescrito via `monkeypatch.setenv` nos testes.

**Estrutura adicionada:**
```
backend/app/pipeline/
  scanner.py     (compute_hash, scan)
  router.py      (route por extensão)
  ingestor.py    (run_pipeline, _process_folder, _copy_direct)
backend/app/routers/sync.py
backend/tests/
  test_scanner.py, test_router.py, test_pipeline.py, test_sync_api.py
```

---

## Etapa 4 — Integração LightRAG ✅ (2026-06-14)

**Branch:** `feat/etapa-4-lightrag` → merged na `main`

**Comportamentos implementados:**
- `LightRAGClient.login()`: POST /login com form, armazena token; credencial inválida → `LightRAGAuthError`.
- `LightRAGClient.trigger_scan()`: POST /documents/scan com `Authorization: Bearer`; sem token → login primeiro.
- Token expirado (401) → re-login uma vez, retry; segundo 401 → `LightRAGScanError`.
- Pipeline (sync route): chama `trigger_scan` apenas quando `processed > 0`; se falhar → `scan_triggered=False` mas não bloqueia.
- `POST /api/sync` agora retorna `scan_triggered` real.

**Testes:** 85 backend verdes (todos mockados — nenhuma chamada real ao LightRAG).

**Decisões:**
- Exceção do LightRAG é capturada e logada; não retorna 5xx — sync sempre completa.
- `LightRAGClient` instanciado dentro da rota (stateless por request). Token em memória por instância.

**Estrutura adicionada:**
```
backend/app/lightrag_client.py  (LightRAGClient, LightRAGAuthError, LightRAGScanError)
backend/tests/test_lightrag_client.py
backend/tests/test_lightrag_integration.py
```

---

## Etapa 5 — Integração Docling ✅ (2026-06-14)

**Branch:** `feat/etapa-5-docling` → merged na `main`

**Comportamentos implementados:**
- `DoclingClient.convert(path)`: POST `/v1/convert/source` com payload correto (sources, options com do_ocr=false); extrai `document.md_content`; erro HTTP/network → `DoclingError`.
- Rota `docling`: arquivo convertido salvo como `{stem}.md` em `INPUT_DIR/<dest_subdir>/...` preservando estrutura relativa.
- `DoclingError` → `failed` com mensagem; lote continua (arquivo direto do mesmo lote é processado).
- Arquivo tipo desconhecido → `failed`, Docling não é chamado.
- Dedup aplica também para docling: mesmo hash → skip, sem reconversão.
- `run_pipeline` aceita `docling_client` opcional; sync route passa `DoclingClient(settings.docling_base_url)`.

**Testes:** 96 backend verdes. 6 frontend verdes.

**Estrutura adicionada:**
```
backend/app/docling_client.py  (DoclingClient, DoclingError)
backend/tests/test_docling_client.py
backend/tests/test_docling_pipeline.py
```

---

## Etapa 6 — Scheduler ✅ (2026-06-14)

**Branch:** `feat/etapa-6-scheduler` → merged na `main`

**Comportamentos implementados:**
- `create_and_configure_scheduler(interval_minutes, job_func)`: retorna `BackgroundScheduler` com job `sync_pipeline` registrado com `IntervalTrigger`.
- Job aponta para `run_sync_job` — mesma lógica do `POST /api/sync`, mas com sessão própria.
- `GET /api/sync/status`: retorna `{last_run: null}` antes do primeiro sync; depois retorna `{last_run, processed, skipped, failed, scan_triggered}`.
- Lifespan do FastAPI: `scheduler.start()` no startup, `scheduler.shutdown(wait=False)` no shutdown — testado via mock.

**Testes:** 104 backend verdes. Sem sleep real — testa configuração do job, não passagem de tempo.

**Decisões:**
- `_last_sync_result` é global de módulo; reset via fixture `autouse` em testes para evitar poluição.
- `run_sync_job` cria e descarta engine/session própria (evita compartilhamento com web requests).
- APScheduler 3.x instalado (`BackgroundScheduler` + `IntervalTrigger`); teste de intervalo usa introspection adaptável.

**Estrutura adicionada:**
```
backend/app/scheduler.py    (create_and_configure_scheduler)
backend/app/routers/sync.py (GET /status + _execute_sync + run_sync_job)
backend/app/main.py         (lifespan com scheduler start/stop)
backend/tests/test_scheduler.py
```

---

## Etapa 7 — Frontend completo ✅ (2026-06-14)

**Branch:** `feat/etapa-7-frontend` → merged na `main`

**Comportamentos implementados (backend):**
- `GET /api/files?status=...&folder_id=...` lista `processed_files` com filtro opcional; retorna ordenado por `created_at desc`.

**Comportamentos implementados (frontend):**
- `StatusPage`: mostra último sync (ou "Never synced"); botão "Sync Now" chama `POST /api/sync`; loading state (`Syncing…`, disabled); atualiza resultado ao concluir; mostra `scan_triggered`.
- `FilesPage`: lista arquivos com badge de status; mostra `error_message` nos `failed`; botões de filtro por status (all/done/failed/processing/skipped); "No files found" quando lista vazia.
- `App.tsx`: navegação por tabs (Status / Folders / Files).

**Testes:** 107 backend + 18 frontend = 125 total, todos verdes.

**Estrutura adicionada:**
```
backend/app/routers/files.py
backend/app/schemas/files.py
frontend/src/components/StatusPage.tsx + StatusPage.test.tsx
frontend/src/components/FilesPage.tsx + FilesPage.test.tsx
frontend/src/App.tsx  (reescrito com navegação)
frontend/src/api.ts   (getSyncStatus, triggerSync, listFiles adicionados)
```

---

## Etapa 8 — Empacotamento e catálogo ✅ (2026-06-14)

**Branch:** `feat/etapa-8-packaging` → merged na `main`

**Artefatos criados (não-TDD — infra/config):**
- `Dockerfile` multi-stage: Node 22 builda o frontend; Python 3.12-slim serve API + estáticos.
- `docker-compose.prod.yml`: serviços `db` (postgres:16) + `app` (rag-orchestrator); volume compartilhado `/DATA/AppData/lightrag/inputs`.
- `.github/workflows/ci.yml`: jobs `test-backend` (pytest com postgres service) + `test-frontend` (vitest) → gate → `build-and-push` (multi-arch amd64/arm64 para ghcr.io, apenas em push na main).
- `Apps/RagOrchestrator/docker-compose.yml` no casaos-appstore: padrão `x-casaos` com `tips.before_install` cobrindo LightRAG, Docling e volume compartilhado.
- `.env.example` com todas as variáveis obrigatórias.
- `backend/app/main.py` atualizado com rota SPA catch-all (`/{full_path:path}`); no-op quando `frontend/dist` ausente (sem impacto nos testes).
- `backend/pyproject.toml` atualizado com `aiofiles>=23.0` (requerido pelo StaticFiles do FastAPI).

**Testes:** 107 backend + 18 frontend = 125 total, todos verdes.

**Decisões:**
- Imagem única (API + frontend estático) para simplificar deploy; sem reverse proxy nginx necessário.
- `CMD`: `alembic upgrade head && uvicorn ...` — migrations rodam no startup do container (idempotente).
- Volume `/DATA/AppData/lightrag/inputs` compartilhado com o app LightRAG do CasaOS.
- `extra_hosts: host.docker.internal:host-gateway` para atingir serviços no host (LightRAG, Docling).
- SPA fallback: serve arquivo real se existir; senão `index.html`; 404 se dist ausente.

**Estrutura adicionada:**
```
Dockerfile
docker-compose.prod.yml
.env.example
.github/workflows/ci.yml
Apps/RagOrchestrator/docker-compose.yml  (casaos-appstore)
```
