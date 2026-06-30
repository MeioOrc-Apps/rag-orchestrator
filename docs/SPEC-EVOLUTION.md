# RAG Orchestrator — OpenSearch Module Spec

## Contexto

O rag-orchestrator (FastAPI + APScheduler + PostgreSQL + React/Vite) passa a usar
OpenSearch como motor de busca full-text (BM25) em substituição ao LightRAG.
A estratégia de retrieval é determinística (lexical), com enriquecimento de query
via LLM no momento da busca e tradução PT→EN no momento da indexação.

Stack de referência: FastAPI, SQLAlchemy 2.0 async, APScheduler, PostgreSQL,
OpenSearch 3.x, Python 3.12.

---

## 1. Schema PostgreSQL

### 1.1 `files` — fonte de verdade para arquivos

```sql
CREATE TABLE files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path            TEXT NOT NULL UNIQUE,        -- path absoluto no host
    filename        TEXT NOT NULL,
    domain          TEXT NOT NULL,               -- ex: 'rpg', 'ti', 'docs'
    file_hash       TEXT NOT NULL,               -- SHA-256 do conteúdo
    file_size_bytes BIGINT NOT NULL,
    mime_type       TEXT,                        -- 'text/markdown', 'application/pdf', etc.
    parse_status    TEXT NOT NULL DEFAULT 'pending'
                    CHECK (parse_status IN ('pending','done','failed')),
    parse_error     TEXT,
    deleted_at      TIMESTAMPTZ,                 -- soft delete; NULL = ativo
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_files_parse_status  ON files (parse_status) WHERE deleted_at IS NULL;
CREATE INDEX idx_files_domain        ON files (domain)       WHERE deleted_at IS NULL;
CREATE INDEX idx_files_hash          ON files (file_hash);
```

**Notas:**
- `file_hash` é a chave de change detection. Se o hash mudar, o sistema deleta os
  chunks antigos, limpa o OpenSearch e reprocessa.
- `deleted_at` é soft delete: o arquivo foi removido do disco ou explicitamente
  excluído via API, mas o histórico permanece no banco.
- `domain` é informado pelo path de origem (ex: arquivos em `/inputs/RPG/` → domain
  `rpg`) ou configurável via API.

---

### 1.2 `chunks` — unidade de indexação

```sql
CREATE TABLE chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id             UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL,          -- ordem dentro do arquivo
    content_original    TEXT NOT NULL,             -- texto extraído, idioma original
    source_language     TEXT NOT NULL              -- 'pt' | 'en' | 'unknown'
                        CHECK (source_language IN ('pt', 'en', 'unknown')),
    content_pt          TEXT,                      -- NULL se source_language = 'en'
    content_en          TEXT,                      -- sempre preenchido após tradução
    char_count          INTEGER NOT NULL,

    -- pipeline statuses
    translation_status  TEXT NOT NULL DEFAULT 'pending'
                        CHECK (translation_status IN
                            ('not_needed','pending','done','failed')),
    translation_error   TEXT,
    translation_model   TEXT,                      -- modelo usado, pra auditoria
    translated_at       TIMESTAMPTZ,

    index_status        TEXT NOT NULL DEFAULT 'pending'
                        CHECK (index_status IN ('pending','done','failed','deleted')),
    index_error         TEXT,
    opensearch_id       TEXT,                      -- _id no OpenSearch
    indexed_at          TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (file_id, chunk_index)
);

CREATE INDEX idx_chunks_file_id           ON chunks (file_id);
CREATE INDEX idx_chunks_translation_status ON chunks (translation_status)
    WHERE translation_status IN ('pending', 'failed');
CREATE INDEX idx_chunks_index_status       ON chunks (index_status)
    WHERE index_status IN ('pending', 'failed');
```

**Lógica de `content_pt` / `content_en`:**

```
source_language = 'pt'
  → content_pt   = content_original
  → content_en   = <tradução via LLM>
  → translation_status = 'done'

source_language = 'en'
  → content_pt   = NULL
  → content_en   = content_original
  → translation_status = 'not_needed'

source_language = 'unknown'
  → trata como 'en' por padrão; registra 'unknown' pra revisão manual
```

---

### 1.3 `translation_settings` — configuração do pipeline de tradução

```sql
CREATE TABLE translation_settings (
    id               SERIAL PRIMARY KEY,
    model            TEXT NOT NULL,           -- ex: 'local:qwen2.5:7b' ou 'openrouter:...'
    prompt_template  TEXT NOT NULL,
    target_language  TEXT NOT NULL DEFAULT 'en',
    batch_size       INTEGER NOT NULL DEFAULT 5,
    enabled          BOOLEAN NOT NULL DEFAULT true,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- seed inicial
INSERT INTO translation_settings (model, prompt_template, target_language)
VALUES (
    'local:qwen2.5:7b',
    'Translate the following text to English. Output only the translation, no preamble:\n\n{text}',
    'en'
);
```

---

### 1.4 `search_query_log` — auditoria de buscas

```sql
CREATE TABLE search_query_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_original   TEXT NOT NULL,
    query_enriched   TEXT,                    -- termos expandidos pelo LLM
    domain_filter    TEXT,                    -- filtro aplicado, se houver
    results_count    INTEGER,
    top_score        FLOAT,
    latency_ms       INTEGER,
    enrichment_used  BOOLEAN NOT NULL DEFAULT false,
    fallback_used    BOOLEAN NOT NULL DEFAULT false,  -- se usou tradução de query
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_query_log_created ON search_query_log (created_at DESC);
```

---

## 2. OpenSearch — Index Mapping

Um índice por domínio: `rag_rpg`, `rag_ti`, `rag_docs` (ou `rag_{domain}`).
Isso isola os domínios sem precisar de instâncias separadas.

```json
PUT /rag_{domain}
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "portuguese_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "portuguese_stop", "portuguese_stemmer"]
        },
        "english_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "english_stop", "english_stemmer"]
        }
      },
      "filter": {
        "portuguese_stop":    { "type": "stop",    "language": "portuguese" },
        "portuguese_stemmer": { "type": "stemmer", "language": "portuguese" },
        "english_stop":       { "type": "stop",    "language": "english"    },
        "english_stemmer":    { "type": "stemmer", "language": "english"    }
      }
    }
  },
  "mappings": {
    "properties": {
      "chunk_id":        { "type": "keyword" },
      "file_id":         { "type": "keyword" },
      "filename":        { "type": "keyword" },
      "domain":          { "type": "keyword" },
      "chunk_index":     { "type": "integer" },
      "source_language": { "type": "keyword" },
      "content_pt": {
        "type": "text",
        "analyzer": "portuguese_analyzer",
        "term_vector": "with_positions_offsets"
      },
      "content_en": {
        "type": "text",
        "analyzer": "english_analyzer",
        "term_vector": "with_positions_offsets"
      },
      "indexed_at": { "type": "date" }
    }
  }
}
```

**Notas:**
- `term_vector: with_positions_offsets` habilita highlighting preciso nos dois campos.
- Sem vetores, sem ML plugin — BM25 puro.
- Um índice por domínio = filtro de domínio gratuito (busca só no índice certo).

---

## 3. Pipelines APScheduler

### 3.1 `scan_job` — detecta arquivos novos e modificados

**Trigger:** cron, a cada 15 minutos (configurável).

**Lógica:**
```
Para cada arquivo em INPUT_DIR (recursivo):
  1. Calcula SHA-256
  2. Busca no banco por path
  3. Novo (não existe):    INSERT em files com parse_status='pending'
  4. Modificado (hash ≠):  marca chunks antigos como index_status='deleted'
                           deleta do OpenSearch por file_id
                           deleta chunks do banco
                           atualiza file_hash, seta parse_status='pending'
  5. Deletado do disco:    seta files.deleted_at=now()
                           marca chunks como index_status='deleted'
                           deleta do OpenSearch por file_id
```

---

### 3.2 `parse_job` — extrai texto e chunka

**Trigger:** cron, a cada 5 minutos; processa arquivos com `parse_status='pending'`.

**Parser:**
O rag-orchestrator já possui sua própria implementação de parsing (PDF, MD, etc.).
O parse_job chama o parser existente — não introduz nova dependência de parser.
O texto extraído é recebido como string pura; o que acontece abaixo é
responsabilidade exclusiva deste módulo.

**Chunking:**
- Tamanho alvo: 1.000 caracteres, overlap de 100 caracteres.
- Quebra preferencialmente em parágrafo (`\n\n`), depois em frase (`.`), nunca no meio de palavra.
- Chunks com menos de 50 caracteres são descartados (cabeçalhos, números de página).

**Detecção de idioma (por arquivo, não por chunk):**

A detecção é feita uma única vez sobre o arquivo completo, antes de gerar os chunks,
e o resultado é propagado para todos os chunks daquele arquivo.

Usar o texto inteiro seria desnecessário e potencialmente enganoso: cabeçalhos,
metadados, sumários no início do arquivo podem conter palavras em idioma diferente
do corpo principal. A estratégia é amostrar o meio do conteúdo extraído:

```python
def detect_language(text: str) -> str:
    total = len(text)
    # ignora os primeiros 25% e os últimos 25% do texto
    start = total // 4
    end   = total - (total // 4)
    sample = text[start:end]

    # limita a amostra a 2.000 caracteres (langdetect não precisa de mais)
    sample = sample[:2000]

    try:
        result = detect_langs(sample)          # retorna lista ordenada por score
        top = result[0]
        if top.lang in ('pt', 'en') and top.prob >= 0.80:
            return top.lang
        return 'unknown'
    except LangDetectException:
        return 'unknown'
```

- Score de confiança < 0.80: marca `source_language='unknown'`, não bloqueia o pipeline.
- `'unknown'` é tratado como `'pt'` no translate_job (traduz pra EN por segurança),
  mas fica registrado separadamente para revisão via `/admin/stats`.

**Saída:** INSERTs em `chunks` com `translation_status='pending'` (ou `'not_needed'` se EN).

---

### 3.3 `translate_job` — traduz chunks PT→EN

**Trigger:** cron, a cada 5 minutos; processa chunks com `translation_status='pending'`.

**Lógica:**
```
Busca chunks pending em batches (batch_size da translation_settings)
Para cada chunk:
  se source_language = 'en':
    content_en = content_original
    translation_status = 'not_needed'
  se source_language = 'pt' ou 'unknown':
    chama LLM com prompt_template
    content_en = resultado
    translation_model = modelo usado
    translated_at = now()
    translation_status = 'done'
  em caso de erro:
    translation_status = 'failed'
    translation_error  = mensagem
    (será retentado na próxima execução do job, até MAX_TRANSLATION_RETRIES)
```

**Configuração de retry:**
- MAX_TRANSLATION_RETRIES = 3 (env var). Após 3 falhas, o chunk fica em `failed`
  e requer intervenção manual via API.

---

### 3.4 `index_job` — indexa no OpenSearch

**Trigger:** cron, a cada 5 minutos; processa chunks com
`translation_status IN ('done','not_needed')` e `index_status='pending'`.

**Lógica:**
```
Busca chunks pending em batches de 100
Para cada batch:
  monta payload _bulk com content_pt e content_en
  POST /_bulk para o índice do domínio correto
  para cada chunk com sucesso:
    index_status = 'done'
    opensearch_id = _id retornado
    indexed_at = now()
  para cada chunk com erro:
    index_status = 'failed'
    index_error  = mensagem
```

---

### 3.5 `delete_job` — limpa deleções pendentes no OpenSearch

**Trigger:** cron, a cada 10 minutos; processa chunks com `index_status='deleted'`.

**Lógica:**
```
Busca opensearch_ids de chunks com index_status='deleted'
POST /_bulk com action 'delete' para cada id
Confirma deleção
Hard-delete dos chunks do banco (ou mantém com flag, decisão de auditoria)
```

---

## 4. API REST (FastAPI)

### 4.1 Busca

```
POST /search
Body: {
  "query": "string",           -- query do usuário
  "domain": "rpg" | "ti" | "docs" | null,  -- null = busca em todos
  "enrich": true,              -- usa LLM pra expandir a query (default: true)
  "limit": 10,
  "offset": 0
}

Response: {
  "query_original": "string",
  "query_enriched": "string | null",
  "results": [
    {
      "chunk_id": "uuid",
      "file_id": "uuid",
      "filename": "string",
      "domain": "string",
      "chunk_index": 0,
      "highlight": "string",   -- trecho com termo destacado
      "score": 1.23
    }
  ],
  "total": 42,
  "latency_ms": 38
}
```

**Lógica de enriquecimento de query:**
```
1. LLM expande a query: adiciona sinônimos, termos relacionados,
   tradução EN caso a query seja PT (ou vice-versa)
   Exemplo: "esquiva" → "esquiva OR evasão OR EVASÃO OR dodge OR evasion"
2. Monta multi_match nos campos content_pt e content_en com os termos OR'd
3. Se results_count = 0 e enrich=true: retenta sem enriquecimento (fallback)
   e sinaliza fallback_used=true no log
4. Grava em search_query_log
```

**Query DSL gerada:**
```json
{
  "query": {
    "multi_match": {
      "query": "{query_enriched}",
      "fields": ["content_pt", "content_en"],
      "type": "best_fields",
      "operator": "or"
    }
  },
  "highlight": {
    "fields": {
      "content_pt": {},
      "content_en": {}
    }
  }
}
```

---

### 4.2 Gestão de arquivos

```
GET  /files                        -- lista arquivos com status
GET  /files/{id}                   -- detalhe de um arquivo e seus chunks
DELETE /files/{id}                 -- soft delete + remove do OpenSearch
POST /files/{id}/reindex           -- força reprocessamento completo
POST /files/{id}/retranslate       -- força retradução dos chunks com falha
```

---

### 4.3 Operações de manutenção

```
POST /admin/reindex-all            -- reprocessa todos os arquivos (use com cuidado)
POST /admin/forcemerge             -- POST /{index}/_forcemerge no OpenSearch
GET  /admin/stats                  -- contagens por status de cada pipeline
GET  /admin/failed                 -- lista chunks/arquivos com falha
POST /admin/retry-failed           -- re-enfileira todos os itens com status='failed'
```

**Resposta de `/admin/stats`:**
```json
{
  "files": {
    "total": 1043,
    "parse_pending": 0,
    "parse_done": 1041,
    "parse_failed": 2,
    "deleted": 3
  },
  "chunks": {
    "total": 28401,
    "translation_pending": 0,
    "translation_done": 19832,
    "translation_not_needed": 8541,
    "translation_failed": 28,
    "index_pending": 0,
    "index_done": 28373,
    "index_failed": 0
  },
  "opensearch": {
    "docs_count": 28373,
    "index_size_mb": 142
  }
}
```

---

## 5. MCP Server

Servidor MCP separado, rodando como processo FastAPI na porta 9700.
Conectável ao Claude Desktop / Claude Code via stdio ou SSE.

### 5.1 Ferramentas expostas

#### `search`
Busca com enriquecimento de query via LLM antes de bater no OpenSearch.

```json
{
  "name": "search",
  "description": "Busca na base de conhecimento (RPG, TI, docs). A query é automaticamente enriquecida com sinônimos e tradução antes da busca.",
  "inputSchema": {
    "query":   { "type": "string", "description": "Pergunta ou termos de busca" },
    "domain":  { "type": "string", "enum": ["rpg","ti","docs"], "description": "Filtro de domínio (opcional)" },
    "limit":   { "type": "integer", "default": 5 }
  }
}
```

#### `list_files`
Lista arquivos indexados, com filtro de domínio e status.

```json
{
  "name": "list_files",
  "description": "Lista os arquivos na base de conhecimento com seus status de indexação.",
  "inputSchema": {
    "domain": { "type": "string" },
    "status": { "type": "string", "enum": ["done","failed","pending"] }
  }
}
```

#### `get_stats`
Retorna o resumo de status dos pipelines (espelha `/admin/stats`).

```json
{
  "name": "get_stats",
  "description": "Retorna contagens de arquivos e chunks por status de pipeline."
}
```

#### `reindex_file`
Força o reprocessamento de um arquivo por nome ou ID.

```json
{
  "name": "reindex_file",
  "description": "Força o reprocessamento completo (parse + tradução + indexação) de um arquivo.",
  "inputSchema": {
    "file_id":  { "type": "string", "description": "UUID do arquivo (alternativo ao filename)" },
    "filename": { "type": "string", "description": "Nome do arquivo (alternativo ao file_id)" }
  }
}
```

### 5.2 Enriquecimento de query (detalhe)

Chamada ao LLM local (configurável via env `ENRICHMENT_MODEL`) com prompt:

```
Você é um assistente de busca. Dado o termo de busca abaixo, gere uma lista de
sinônimos, termos relacionados e a tradução em inglês (se estiver em português)
ou em português (se estiver em inglês). Retorne apenas os termos separados por
espaço, sem explicação, sem pontuação extra.

Termo: {query}
```

Saída esperada: `esquiva evasão dodge evasion "esquiva corporal"`
O MCP monta a query OpenSearch com esses termos em OR.

---

## 6. Variáveis de Ambiente

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/rag

# OpenSearch
OPENSEARCH_HOST=http://opensearch:9200
OPENSEARCH_INDEX_PREFIX=rag                  # índices: rag_rpg, rag_ti, rag_docs

# Pipeline
INPUT_DIR=/data/inputs
SCAN_INTERVAL_MINUTES=15
PARSE_INTERVAL_MINUTES=5
TRANSLATE_INTERVAL_MINUTES=5
INDEX_INTERVAL_MINUTES=5
MAX_TRANSLATION_RETRIES=3
CHUNK_SIZE=1000
CHUNK_OVERLAP=100

# Tradução
ENRICHMENT_MODEL=local:qwen2.5:7b            # ou openrouter:meta-llama/llama-4-scout:free
OLLAMA_HOST=http://host.docker.internal:11434

# MCP Server
MCP_PORT=9700
```

---

## 7. Decisões registradas

| Decisão | Escolha | Racional |
|---|---|---|
| Motor de busca | OpenSearch (BM25) | Determinístico, sem risco de obsolescência de modelo |
| Estratégia de tradução | Index-time PT→EN | Busca instantânea, sem LLM no caminho crítico |
| Parser | Implementação existente no orquestrador | Já validado, sem reintroduzir dependência |
| Detecção de idioma | langdetect, amostra do meio do arquivo (25%–75%, max 2.000 chars) | Evita falsa detecção por metadados/cabeçalhos no início; detecta uma vez por arquivo e propaga para todos os chunks |
| Isolamento de domínio | Um índice por domínio | Filtro gratuito, sem workspace hack |
| Enriquecimento de query | LLM local, query-time | Output descartável, sem risco de obsolescência |
| Fonte de verdade | PostgreSQL | OpenSearch é índice derivado, reconstruível |
| Change detection | SHA-256 do arquivo | Detecta modificações sem polling por data |
| Retry de falhas | Status explícito + job periódico | Sem fila externa (sem Redis/Celery) |

---

## 8. Pendências / Out of scope desta spec

- UI React do rag-orchestrator (tela de status dos pipelines, busca manual)
- Autenticação na API REST (coberta pelo Save State / JWT já existente)
- Suporte a DOCX (pode ser adicionado ao parse_job com python-docx, sem mudança de schema)
- Chunking semântico (substituição do chunking por tamanho por divisão por seção/heading)
- Busca híbrida vetorial (descartada conscientemente nesta versão)