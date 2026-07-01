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

---

## Etapa 9 — Roteamento multiformato ✅ (2026-06-15)

**Branch:** `feat/etapa-9-multiformat-routing`

**Comportamentos implementados:**
- `pdf_direct`: `is_digital_pdf(path, min_text_page_ratio=0.5)` detecta PDFs digitais por fração de páginas com texto (`get_text().strip() > 10 chars`). `convert_to_markdown` usa `pymupdf4llm.to_markdown`.
- `markitdown_client`: singleton `MarkItDown()`; `convert_to_markdown` retorna `.markdown` (não `.text_content`, deprecado).
- Router recebe caminho completo (não extensão); PDF decide por conteúdo: digital→`pdf_direct`, escaneado→`docling`. Desconhecido→`unsupported` (sem raise).
- Pipeline despacha as 4 rotas; `unsupported` registra `failed` e segue o lote (sem `ValueError`).
- Dedup por hash válido em todas as 4 rotas.

**Novos tipos aceitos pelo sistema:**
- `direct`: rst, tex, csv, py, js, ts, jsx, tsx, json, yaml, yml, toml, ini, cfg, sql, sh, bash, xml, css, go, rs, java, c, cpp, h, rb, php, lua (além de md/txt já existentes)
- `markitdown`: docx, doc, pptx, ppt, xlsx, html, htm (antes iam para Docling)
- `pdf_direct`: pdf digital (antes ia para Docling)
- `docling`: somente pdf escaneado e imagens (png, jpg, jpeg, tiff, bmp, webp)

**Testes:** 71 novos testes (41 unit + 30 integração) adicionados; suíte completa requer DB.

**Decisões:**
- `pymupdf4llm>=0.0.17` e `markitdown[all]>=0.1.0` adicionados ao `pyproject.toml`.
- Teste de PDF 0-páginas usa mock (pymupdf recusa salvar PDF vazio no disco).
- `test_docling_pipeline.py`: fixture `autouse` mock `is_digital_pdf=False` para garantir que PDFs falsos (fixtures) vão para Docling. Teste de DOCX removido (DOCX→markitdown agora).
- Rotas `pdf_direct` e `markitdown` capturam `Exception` genérica (→`failed`); consistente com "falha não aborta lote".

**Estrutura adicionada:**
```
backend/app/pdf_direct.py
backend/app/markitdown_client.py
backend/tests/test_pdf_direct.py
backend/tests/test_markitdown_client.py
backend/tests/test_multiformat_pipeline.py
```

**Modificado:**
```
backend/pyproject.toml              (novas deps)
backend/app/pipeline/router.py      (4 rotas, assinatura path)
backend/app/pipeline/ingestor.py    (dispatch 4 rotas + unsupported)
backend/tests/test_router.py        (novos casos, nova API)
backend/tests/test_docling_pipeline.py  (autouse mock, removido docx test)
docs/SPEC.md                        (seção roteamento multiformato)
```

---

## Etapa 10 — Schema & Foundation (OpenSearch Module) ✅ (2026-06-30)

**Branch:** `feat/etapa-10-schema-foundation`

**Comportamentos implementados:**
- Config: remove vars `LIGHTRAG_BASE_URL/USERNAME/PASSWORD/INPUT_DIR`; adiciona `OPENSEARCH_HOST` (required), renomeia `LIGHTRAG_INPUT_DIR` → `INPUT_DIR`; adiciona `OPENSEARCH_INDEX_PREFIX` (default 'rag'), `PARSE/TRANSLATE/INDEX_INTERVAL_MINUTES`, `MAX_TRANSLATION_RETRIES`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `ENRICHMENT_MODEL`, `OLLAMA_HOST`, `MCP_PORT`.
- LightRAG removido: `lightrag_client.py` deletado; `sync.py` remove trigger_scan (scan_triggered sempre False até etapa 12).
- Novos models: `File`, `Chunk`, `TranslationSettings`, `SearchQueryLog` em `app/models.py` (ao lado dos legados `ProcessedFile`, `SyncState` que ficam até etapa 12).
- Migration 003: cria `files`, `chunks`, `translation_settings`, `search_query_log`; seed de `TranslationSettings` (idempotente); downgrade remove só as novas tabelas.

**Testes:** 166 passed (todos verdes).

**Decisões:**
- Migration 003 é aditiva — não dropa `processed_files`/`sync_state`. Drop acontece em etapa 12 quando o pipeline for substituído pelo scan_job/parse_job.
- `ProcessedFile`, `SyncState` permanecem em models.py temporariamente (legacy até etapa 12).
- `scan_triggered` sempre False no sync.py até etapa 12 implementar o novo scan_job.
- OpenSearch IP do ambiente local: `192.168.3.100` (porta a confirmar — 9200 padrão ou 5601 para dashboards).

**Estrutura adicionada:**
```
backend/alembic/versions/003_opensearch_module.py
backend/tests/test_models.py
backend/tests/test_migrations.py   (reescrito)
backend/tests/test_config.py       (reescrito)
```

**Removido:**
```
backend/app/lightrag_client.py
backend/tests/test_lightrag_client.py
backend/tests/test_lightrag_integration.py
backend/tests/test_e2e_integration.py  (testava LightRAG real)
```

---

## Etapa 11 — OpenSearch Client ✅ (2026-06-30)

**Branch:** `feat/etapa-11-opensearch-client` → merged na `main`

**Comportamentos implementados:**
- `OpenSearchClient.ensure_index(domain)`: cria `{prefix}_{domain}` com analyzers PT+EN (custom stemmer + stop words), `term_vector=with_positions_offsets`; HEAD antes do PUT; idempotente.
- `OpenSearchClient.bulk_index(domain, docs)`: POST `/_bulk` ndjson; retorna `(successes, errors)` como `(chunk_id, os_id)` / `(chunk_id, reason)`.
- `OpenSearchClient.bulk_delete(domain, ids)`: POST `/_bulk` delete; retorna ids confirmados deletados.
- `OpenSearchClient.search(query, domain, limit, offset)`: `multi_match` em `content_pt`+`content_en`; highlight; `domain=None` → `rag_*` (todos os índices).
- `OpenSearchClient.get_index_stats(domain)`: retorna `{docs_count, index_size_mb}`; 404 → zeros.

**Testes:** 168 passed, 1 skipped (integration real — requer `TEST_OPENSEARCH_HOST`). 11 unit tests com `unittest.mock.patch` em `httpx.Client`.

**Decisões:**
- Unit tests em `test_opensearch_client.py` mocam `httpx.Client` inteiro; sem deps externas.
- Integration tests em `test_opensearch_integration.py` usam `TEST_OPENSEARCH_HOST` env var (≠ `OPENSEARCH_HOST` do conftest); skip no module level se ausente.
- Prefixo `rag_test` em integração para não poluir índices reais.
- `_json_line()` helper usa `json.dumps(default=str)` para serializar UUID/datetime.

**Estrutura adicionada:**
```
backend/app/opensearch_client.py
backend/tests/test_opensearch_client.py
backend/tests/test_opensearch_integration.py
```

---

## Etapa 12 — scan_job ✅ (2026-06-30)

**Branch:** `feat/etapa-12-scan-job` → merged na `main`

**Comportamentos implementados:**
- `scan_job.run_scan(db, folders)`: escaneia pastas ativas, insere/atualiza/soft-deleta na tabela `files`; retorna `{scanned, inserted, updated, deleted, skipped}`.
- Novo arquivo → INSERT `files` com `parse_status='pending'`, `domain=folder.dest_subdir`.
- Arquivo modificado (hash diferente) → chunks marcados `index_status='deleted'`, hash atualizado, `parse_status='pending'`.
- Arquivo removido do disco → `files.deleted_at=now()`, chunks marcados `index_status='deleted'`.
- Arquivo inalterado → skip (sem escrita).
- `POST /api/sync` agora chama `run_scan()` e retorna novo shape.
- Migration 004: dropa `processed_files` e `sync_state` (tabelas legadas).

**Removido:**
- `ProcessedFile`, `SyncState` de `models.py`
- `pipeline/ingestor.py` (copiava arquivos para INPUT_DIR → LightRAG, substituído por scan_job)
- `lightrag_client.py` (remanescente não removido em etapa 10, agora deletado)
- `test_docling_pipeline.py`, `test_multiformat_pipeline.py`, `test_files_api.py` (testavam comportamento do ingestor legado)

**Testes:** 153 passed (1 skipped — integration opensearch).

**Decisões:**
- `files` não tem `folder_id` — identificação de qual pasta originou um arquivo é por `path.startswith(folder.host_path)`.
- `routers/files.py` stubado (retorna lista vazia) até etapa 16 reescrever a API de arquivos.
- `test_pipeline.py` reescrito para testar scanner/router primitivos em vez do ingestor.
- `crud/folders.py`: `delete_folder` não mais cascateia ProcessedFile; `files` table não tem FK para `watched_folders`.

**Estrutura adicionada:**
```
backend/app/jobs/__init__.py
backend/app/jobs/scan_job.py
backend/alembic/versions/004_drop_legacy_tables.py
backend/tests/test_scan_job.py
```

---

## Etapa 13 — parse_job (chunking + language detection) ✅ (2026-06-30)

**Branch:** `feat/etapa-13-parse-job` → merged na `main`

**Comportamentos implementados:**
- `detect_language(text)`: amostra os 25–75% centrais do texto (máx 2000 chars); usa `langdetect` com `DetectorFactory.seed=0` (determinístico); threshold 0.80; retorna `'pt'|'en'|'unknown'`; texto vazio/curto → `'unknown'`.
- `chunk_text(text, size, overlap)`: prefere quebra em `\n\n`, fallback em `.`, fallback em espaço; nunca corta palavra; descarta pedaços < 50 chars.
- `run_parse(db)`: busca `files` com `parse_status='pending'` e `deleted_at IS NULL`; despacha via `route()`; insere `Chunk` rows; `translation_status='not_needed'` para EN, `'pending'` para PT/unknown; em erro: `parse_status='failed'` com mensagem, continua o lote.

**Nova dep:** `langdetect>=1.0.9` adicionado a `pyproject.toml`.

**Testes:** 173 passed, 1 skipped. 20 novos testes em `test_parse_job.py`.

**Decisões:**
- Todos os 5 comportamentos TDD implementados em ciclo único (detect_language + chunk_text + run_parse são mutuamente dependentes; separá-los causaria falhas de import na suíte).
- `_MIN_CHUNK_CHARS=50`: aplica-se a pedaços resultantes de split, não ao documento inteiro.
- `_read_file` despacha para pdf_direct/markitdown/docling/direct conforme `route()`; `unsupported` levanta `ValueError` → `parse_status='failed'`.
- Settings instanciado dentro do `run_parse` para respeitar overrides de env nos testes.

**Estrutura adicionada:**
```
backend/app/jobs/parse_job.py
backend/tests/test_parse_job.py
```

---

## Etapa 14 — translate_job ✅ (2026-06-30)

**Branch:** `feat/etapa-14-translate-job` → merged na `main`

**Comportamentos implementados:**
- `LLMClient('local:model')`: backend `ollama`, chama `POST {OLLAMA_HOST}/api/generate`, retorna `response`. Erro HTTP → `LLMError`.
- `LLMClient('openrouter:model')`: backend `openrouter`, chama `POST https://openrouter.ai/api/v1/chat/completions` com `Authorization: Bearer`, retorna `choices[0].message.content`. Erro HTTP → `LLMError`.
- Prefixo desconhecido → `ValueError`.
- `run_translate(db)`: busca `TranslationSettings` enabled; processa `not_needed` (copia `content_original` → `content_en`, sem LLM) e `pending` (chama LLM) em lotes de `batch_size`.
- Sucesso: `content_en` set, `translation_status='done'`, `translation_model` e `translated_at` registrados.
- Falha: retenta até `MAX_TRANSLATION_RETRIES` (ou `max_retries` param); após max → `translation_status='failed'`, `translation_error` set.
- Chunks já `done` ignorados; `LLMClient` não instanciado se não há chunks `pending`.

**Testes:** 193 passed, 1 skipped. 20 novos testes em `test_llm_client.py` (unit, mocked httpx) e `test_translate_job.py` (integration, mocked LLMClient).

**Estrutura adicionada:**
```
backend/app/llm_client.py
backend/app/jobs/translate_job.py
backend/tests/test_llm_client.py
backend/tests/test_translate_job.py
```

---

## Etapa 15 — index_job + delete_job ✅ (2026-06-30)

**Branch:** `feat/etapa-15-index-delete-jobs` → merged na `main`

**Comportamentos implementados:**
- `index_job.run_index(db)`: busca chunks com `translation_status IN ('done','not_needed')` e `index_status='pending'`; agrupa por `domain`; chama `ensure_index(domain)` antes do primeiro batch; `bulk_index` em lotes de 100; sucesso → `index_status='done'`, `opensearch_id`, `indexed_at`; falha parcial → `index_status='failed'`, `index_error`; successes committed mesmo se há falhas.
- `delete_job.run_delete(db)`: busca chunks com `index_status='deleted'`; agrupa por domain; chama `bulk_delete` apenas para chunks com `opensearch_id`; hard-delete do DB somente após confirmação do OS; chunks sem `opensearch_id` hard-deletados diretamente sem chamada ao OS.

**Testes:** 208 passed, 1 skipped. 15 novos testes em `test_index_job.py` e `test_delete_job.py` (integration, mocked OpenSearchClient).

**Decisões:**
- `index_job` usa `join(Chunk.file)` para acessar `domain` sem N+1 queries.
- `delete_job` retorna `{deleted_from_os, deleted_from_db}` para distinguir confirmações do OS vs remoções diretas.
- Se `bulk_delete` não confirma um `opensearch_id`, chunk permanece no DB (defensive — pode ser retentado).

**Estrutura adicionada:**
```
backend/app/jobs/index_job.py
backend/app/jobs/delete_job.py
backend/tests/test_index_job.py
backend/tests/test_delete_job.py
```

---

## Etapa 16 — Search API + Files API ✅ (2026-06-30)

**Branch:** `feat/etapa-16-search-files-api` → merged na `main`

**Comportamentos implementados:**
- `POST /api/search {query, domain?, enrich, limit, offset}`: LLM enriquece query via `enrichment_model`; fallback para query original se 0 resultados ou erro de LLM; log em `search_query_log` a cada chamada.
- `GET /api/files`: paginado, filtrável por `domain` e `parse_status`, exclui soft-deleted.
- `GET /api/files/{id}`: detalhe + `chunks: {total, done, pending, failed, deleted}`.
- `DELETE /api/files/{id}`: soft-delete + marca chunks `index_status='deleted'`.
- `POST /api/files/{id}/reindex`: hard-delete chunks + `parse_status='pending'`.
- `POST /api/files/{id}/retranslate`: reseta chunks `translation_status='failed'` → `'pending'`.

**Testes:** 237 passed, 1 skipped. 29 novos testes em `test_search_api.py` e `test_files_api.py`.

**Estrutura adicionada:**
```
backend/app/routers/search.py
backend/app/schemas/search.py
backend/tests/test_search_api.py
backend/tests/test_files_api.py
```

**Modificado:**
```
backend/app/routers/files.py   (reescrito — saiu do stub para implementação completa)
backend/app/schemas/files.py   (adicionados FileDetailResponse, ChunksSummary)
backend/app/main.py            (registra search_router)
```
