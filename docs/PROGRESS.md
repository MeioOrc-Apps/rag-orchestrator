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

## Etapa 2 — CRUD de pastas rastreáveis (pendente)

**Próximos comportamentos:**
- Model `WatchedFolder` persiste com `owner_id` do seed
- `POST /api/folders` cria e retorna 201
- Validação `host_path` vazio → 422; `dest_subdir` com `..` ou path absoluto → 422
- `GET /api/folders` lista só do owner default
- `GET /api/folders/{id}` detalhe; inexistente → 404
- `PATCH /api/folders/{id}` atualiza campos editáveis
- `DELETE /api/folders/{id}` remove; GET depois → 404
- Frontend: lista + formulário de criação (Vitest)
