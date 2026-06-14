# PLAN.md — RAG Orchestrator

Implementação incremental em TDD. Cada etapa segue red-green-refactor (ver `AGENTS.md`). Implemente UMA etapa por vez. Não avance sem a suíte verde.

Cada etapa lista os **comportamentos** a cobrir. Para cada comportamento: escreva o teste (RED), implemente o mínimo (GREEN), refatore.

---

## Etapa 1 — Fundação

**Objetivo:** repo, infra de dev, banco e migrations iniciais.

Setup (não-TDD, infraestrutura):
- Monorepo com `backend/` e `frontend/`.
- `docker-compose.yml` de dev: serviço `postgres` + serviço `backend`.
- `backend/pyproject.toml` com deps e dev-deps (pytest, pytest-asyncio).
- `app/config.py` (pydantic-settings), `app/database.py` (engine/session/Base).
- Alembic configurado.

Comportamentos (TDD):
- `config` carrega variáveis de ambiente obrigatórias e falha claramente se faltar.
- conexão com o banco de teste abre e fecha sessão.
- migration inicial cria as 3 tabelas (`users`, `watched_folders`, `processed_files`) com as constraints do SPEC.
- migration reverte (downgrade) sem erro.
- seed cria o usuário default a partir de `DEFAULT_OWNER_USERNAME` e é idempotente (rodar 2x não duplica).

**DoD:** `pytest` verde; `alembic upgrade head` e `downgrade base` funcionam; seed idempotente testado.

---

## Etapa 2 — CRUD de pastas rastreáveis

**Objetivo:** gerenciar `watched_folders` via API.

Comportamentos (TDD):
- model `WatchedFolder` persiste e recupera com `owner_id` do seed.
- `POST /api/folders` cria pasta válida e retorna 201 + corpo.
- validação: `host_path` vazio → 422.
- validação: `dest_subdir` com `..` ou path absoluto → 422.
- `GET /api/folders` lista só pastas do owner default.
- `GET /api/folders/{id}` retorna detalhe; id inexistente → 404.
- `PATCH /api/folders/{id}` atualiza `enabled`/`recursive`/`dest_subdir`.
- `DELETE /api/folders/{id}` remove; depois GET → 404.

Frontend (TDD com Vitest):
- página Folders renderiza lista vinda da API (mockada).
- formulário de criação chama o endpoint e atualiza a lista.

**DoD:** suíte backend e frontend verdes; CRUD completo coberto.

---

## Etapa 3 — Pipeline core (sem Docling)

**Objetivo:** detectar, deduplicar e ingerir arquivos `.md`/`.txt` direto na INPUT_DIR. Ainda sem LightRAG, sem Docling.

Comportamentos (TDD):
- `scanner.compute_hash(file)` retorna hash estável para mesmo conteúdo; muda se conteúdo muda.
- `scanner.scan(folder)` lista arquivos; respeita `recursive=false` (não desce subpastas).
- skip: arquivo já em `processed_files` com mesmo hash e status=done não é reprocessado.
- `router_service.route(ext)` retorna `direct` para `.md/.txt/.markdown`, `docling` para pdf/docx/etc, e levanta/registra desconhecido.
- rota `direct`: copia arquivo para `INPUT_DIR/<dest_subdir>/...` preservando estrutura.
- registro: cria `processed_file` com status `processing` → `done`; em erro de I/O → `failed` com mensagem.
- falha em um arquivo não impede os demais do lote.
- `POST /api/sync` executa o pipeline e retorna `{processed, skipped, failed, scan_triggered:false}` (scan vem na etapa 4).

Use `tmp_path` do pytest para simular pastas de origem e INPUT_DIR.

**DoD:** pipeline ingere `.md/.txt` com dedup e tratamento de erro, tudo testado.

---

## Etapa 4 — Integração LightRAG

**Objetivo:** disparar o scan após a ingestão.

Comportamentos (TDD, LightRAG mockado):
- `lightrag_client.login()` faz POST /login e guarda o token; erro de credencial → exceção tratada.
- `lightrag_client.trigger_scan()` envia POST /documents/scan com Bearer; sucesso retorna ok.
- token expirado / 401 → re-login automático uma vez, depois falha clara.
- pipeline chama `trigger_scan` ao fim quando houve ao menos 1 arquivo novo; não chama se nada mudou.
- `POST /api/sync` agora retorna `scan_triggered` refletindo o real.

**DoD:** integração coberta com mock; lógica de re-login testada; sem chamadas reais nos testes unitários.

---

## Etapa 5 — Integração Docling

**Objetivo:** converter PDF/DOCX/etc para Markdown via Docling antes de depositar na INPUT_DIR.

Comportamentos (TDD, Docling mockado):
- `docling_client.convert(path)` monta o payload do SPEC e extrai `document.md_content` da resposta.
- erro HTTP do Docling → exceção tratada; arquivo marcado `failed`, lote continua.
- rota `docling`: arquivo convertido é salvo como `.md` em `INPUT_DIR/<dest_subdir>/...` com nome derivado do original.
- arquivo de tipo desconhecido → `failed` com mensagem, sem chamar Docling.
- dedup vale também para rota docling (mesmo hash não reconverte).

**DoD:** conversão coberta com mock; roteamento direct vs docling testado de ponta a ponta (com I/O em tmp_path e HTTP mockado).

---

## Etapa 6 — Scheduler

**Objetivo:** rodar o pipeline automaticamente a cada `SCAN_INTERVAL_MINUTES`.

Comportamentos (TDD):
- scheduler registra o job com o intervalo de config.
- job dispara a mesma função de pipeline do `/api/sync`.
- `GET /api/sync/status` retorna timestamp e contagens do último run (manual ou agendado).
- start/stop do scheduler no lifespan não vaza (testável via app startup/shutdown).

Evite `sleep` real nos testes: teste a configuração do job e a função-alvo, não a passagem de tempo.

**DoD:** agendamento configurado e testado sem depender de relógio real; status persistido.

---

## Etapa 7 — Frontend completo

**Objetivo:** UI de status e arquivos.

Comportamentos (TDD com Vitest):
- página Status mostra último sync e botão "Sincronizar agora" que chama `POST /api/sync`.
- estado de loading enquanto o sync roda; atualização ao concluir.
- página Files lista processed_files com filtro por status; mostra mensagem de erro nos `failed`.

**DoD:** páginas cobertas; fluxo de sync manual end-to-end (API mockada) testado.

---

## Etapa 8 — Empacotamento e catálogo

**Objetivo:** imagem de produção e entrada no casaos-appstore.

Setup (não-TDD):
- `Dockerfile` de produção (backend serve API + estáticos do frontend buildado, ou dois serviços).
- `docker-compose.prod.yml`.
- GitHub Action: rodar a suíte de testes (gate) → buildar imagem → publicar.
- Entrada `Apps/rag-orchestrator/docker-compose.yml` no casaos-appstore, padrão `x-casaos` (espelhar lightrag/docling).

**DoD:** CI roda testes antes de publicar; imagem sobe; app aparece no catálogo.

---

## Nota sobre a ordem

A etapa 3 já entrega valor: ingestão de Markdown funciona sem Docling nem scheduler. A 4 conecta o LightRAG. A 5 adiciona PDF. Em qualquer ponto a partir da 4, o sistema é utilizável manualmente via `/api/sync`. O scheduler (6) só automatiza o que já funciona.
