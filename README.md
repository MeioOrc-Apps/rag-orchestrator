# RAG Orchestrator

Orquestrador de ingestão de documentos para o LightRAG. Vigia pastas (agendado + manual), roteia por tipo (MD/TXT direto; PDF/DOCX via Docling), deposita Markdown na INPUT_DIR do LightRAG e dispara o scan.

## Documentação

| Arquivo | Papel |
|---|---|
| `CLAUDE.md` | Regras de execução, carregadas automaticamente pelo Claude Code a cada sessão. TDD estrito + git workflow. |
| `docs/SPEC.md` | Arquitetura, stack, schema, contratos de API e integrações. Fonte de verdade técnica. |
| `docs/PLAN.md` | 8 etapas incrementais em TDD. Uma por vez. |
| `docs/PROGRESS.md` | Log de progresso entre sessões (gerado durante o desenvolvimento). Ponte de memória após cada `/clear`. |

## Como desenvolver com Claude Code

1. O `CLAUDE.md` carrega sozinho — define que o projeto é TDD: teste falhando antes de qualquer código.
2. Abra `docs/PLAN.md`, identifique a etapa atual (via `docs/PROGRESS.md`).
3. Branch por etapa, red-green-refactor, um commit por ciclo (Conventional Commits).
4. Etapa concluída + suíte verde → atualiza `PROGRESS.md`, merge local, `/clear`, próxima etapa.
5. Trabalho fica local; push só com autorização.

## Stack

FastAPI + APScheduler + PostgreSQL + React/Vite. Monorepo (`backend/`, `frontend/`).

## Status

Em implementação. Ver `docs/PROGRESS.md` para a etapa corrente.
