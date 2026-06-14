# SPEC.md — RAG Orchestrator

## Visão geral

Serviço que orquestra a ingestão de documentos para o LightRAG. Vigia pastas configuradas (agendado + trigger manual), detecta arquivos novos ou alterados, roteia por tipo (MD/TXT direto; PDF/DOCX e outros via Docling para conversão em Markdown), deposita o resultado na pasta de inputs do LightRAG e dispara o scan de indexação.

## Escopo de usuário

**Single-user agora, schema preparado para multi depois.** Todas as tabelas de domínio carregam `owner_id` desde o início, apontando para um usuário default (seed). Não há login nem gestão de usuários nesta fase. O schema não exigirá migração estrutural para ganhar multi-user depois.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Scheduler | APScheduler (embutido no processo FastAPI, iniciado no lifespan) |
| Banco | PostgreSQL |
| ORM / migrations | SQLAlchemy + Alembic |
| Cliente HTTP | httpx |
| Config | pydantic-settings (via env vars) |
| Frontend | React + Vite + TypeScript |
| Testes backend | pytest, pytest-asyncio |
| Testes frontend | Vitest + React Testing Library |

## Integrações externas (HTTP)

### Docling Serve
- Base: `DOCLING_BASE_URL` (ex: `http://host:5001`)
- Endpoint: `POST /v1/convert/source`
- Payload (PDF de texto, OCR desligado):
  ```json
  {
    "sources": [{"kind": "file", "path": "<caminho-no-container-docling>"}],
    "options": {"to_formats": ["md"], "do_ocr": false, "pdf_backend": "dlparse_v2"}
  }
  ```
- Resposta: JSON contendo o markdown em `document.md_content`.
- Nota: usar o endpoint `source` (path/URL), não `file` (multipart), que ignora opções de OCR.

### LightRAG
- Base: `LIGHTRAG_BASE_URL` (ex: `http://host:9621`)
- Auth: `POST /login` (form `username`/`password`) → retorna JWT. Usar `Authorization: Bearer <token>` nas chamadas seguintes.
- Endpoint usado: `POST /documents/scan` (dispara indexação recursiva da INPUT_DIR).
- O orquestrador NÃO faz upload via API. Escreve os `.md` diretamente na INPUT_DIR (volume compartilhado) e só chama o scan.

## Fluxo de ingestão

```
para cada watched_folder habilitada:
  varre (recursivo se configurado)
  para cada arquivo:
    calcula content_hash
    existe processed_file com mesmo (owner_id, source_path, content_hash) e status=done? 
      sim -> SKIP (registra status=skipped se ainda não houver registro done)
      não -> roteia por extensão:
               .md / .txt           -> route=direct  -> copia para INPUT_DIR/<dest_subdir>/...
               .pdf .docx .pptx ...  -> route=docling -> POST Docling -> salva .md em INPUT_DIR/<dest_subdir>/...
             registra processed_file (status: processing -> done | failed)
após todos os novos:
  LightRAG: login -> POST /documents/scan
  registra resultado
```

## Schema do banco

### users
| coluna | tipo | constraints |
|---|---|---|
| id | UUID | PK |
| username | text | unique, not null |
| created_at | timestamptz | not null, default now() |

### watched_folders
| coluna | tipo | constraints |
|---|---|---|
| id | UUID | PK |
| owner_id | UUID | FK users.id, not null |
| host_path | text | not null |
| dest_subdir | text | not null |
| recursive | boolean | not null, default true |
| enabled | boolean | not null, default true |
| created_at | timestamptz | not null, default now() |

### processed_files
| coluna | tipo | constraints |
|---|---|---|
| id | UUID | PK |
| owner_id | UUID | FK users.id, not null |
| folder_id | UUID | FK watched_folders.id, not null |
| source_path | text | not null |
| dest_path | text | nullable |
| content_hash | text | not null |
| file_type | text | not null |
| route | text | not null ('direct' \| 'docling') |
| status | text | not null ('pending'\|'processing'\|'done'\|'failed'\|'skipped') |
| error_message | text | nullable |
| processed_at | timestamptz | nullable |
| created_at | timestamptz | not null, default now() |

Índice único: (`owner_id`, `source_path`, `content_hash`).

## Contratos da API (backend)

### Pastas
- `GET /api/folders` → lista watched_folders do owner default
- `POST /api/folders` → cria. Body: `{host_path, dest_subdir, recursive, enabled}`. Valida host_path não vazio, dest_subdir sem `..` nem path absoluto.
- `GET /api/folders/{id}` → detalhe
- `PATCH /api/folders/{id}` → atualiza campos editáveis
- `DELETE /api/folders/{id}` → remove

### Sync
- `POST /api/sync` → dispara o pipeline manualmente. Retorna resumo: `{processed, skipped, failed, scan_triggered}`.
- `GET /api/sync/status` → último resultado de sync (timestamp, contagens)

### Arquivos
- `GET /api/files?status=...&folder_id=...` → lista processed_files com filtro opcional

## Variáveis de ambiente

```
DATABASE_URL=postgresql+psycopg://orchestrator:senha@postgres:5432/orchestrator
DOCLING_BASE_URL=http://host:5001
LIGHTRAG_BASE_URL=http://host:9621
LIGHTRAG_USERNAME=sergio
LIGHTRAG_PASSWORD=...
LIGHTRAG_INPUT_DIR=/data/lightrag_inputs
SCAN_INTERVAL_MINUTES=30
DEFAULT_OWNER_USERNAME=sergio
```

## Regras de roteamento por extensão

- `direct` (copiar sem conversão): `.md`, `.txt`, `.markdown`
- `docling` (converter): `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, imagens
- desconhecido: registrar `failed` com mensagem clara, não travar o pipeline

## Decisões de design

1. Sem watch reativo. Detecção agendada (APScheduler) + manual (`POST /api/sync`).
2. Skip por hash de conteúdo, não por mtime.
3. Orquestrador escreve direto na INPUT_DIR do LightRAG e só chama o scan.
4. `owner_id` em todas as tabelas de domínio desde o início (usuário seed).
5. APScheduler no lifespan do FastAPI; um container de backend.
6. Falha em um arquivo não aborta o lote; registra `failed` e segue.
