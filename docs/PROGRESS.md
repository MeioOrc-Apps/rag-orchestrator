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

## Etapa 5 — Integração Docling (pendente)
