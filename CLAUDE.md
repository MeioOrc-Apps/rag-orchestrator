# CLAUDE.md — RAG Orchestrator

Memória durável do projeto. Carregada automaticamente pelo Claude Code no início de cada sessão e após cada `/clear`. **Esta é a fonte de regras de execução.**

## Princípio inegociável: TDD (Test-Driven Development)

Projeto desenvolvido em TDD estrito. Para CADA unidade de comportamento:

1. **RED** — escreva o teste primeiro. Rode e confirme que FALHA pelo motivo certo (comportamento ausente, não erro de import).
2. **GREEN** — escreva o MÍNIMO de código para o teste passar. Nada além.
3. **REFACTOR** — limpe o código mantendo os testes verdes.

Regras:
- NUNCA código de produção sem um teste falhando que o exija.
- NUNCA mais teste do que o suficiente para falhar.
- NUNCA mais código do que o suficiente para passar.
- Ao implementar uma função, o teste vem ANTES, no mesmo passo, mostrado falhando antes da implementação.

## Fluxo por etapa (com quebra de sessão)

O projeto é construído etapa a etapa (ver `docs/PLAN.md`). Cada etapa roda idealmente em **contexto limpo** para evitar degradação:

1. No início da sessão/etapa: este `CLAUDE.md` já está carregado. Leia também `docs/SPEC.md` e `docs/PROGRESS.md` para saber onde o trabalho parou.
2. Identifique a etapa atual no `docs/PLAN.md`. Implemente APENAS ela.
3. Crie a branch da feature (ver Git workflow).
4. Para cada comportamento: red-green-refactor, um commit por ciclo.
5. Ao concluir a etapa com a suíte verde: atualize `docs/PROGRESS.md`, faça merge na `main` (local), e execute **`/clear`** antes de iniciar a próxima etapa.
6. Após o `/clear`, este arquivo recarrega automaticamente; releia `docs/PROGRESS.md` para retomar o contexto e siga para a próxima etapa.

> O `/clear` entre etapas é intencional: cada feature começa com contexto fresco. O `PROGRESS.md` é a ponte de memória entre sessões.

Para isolar trabalho pesado sem poluir o contexto principal, considere delegar verificações ou leituras extensas a um **subagente** (o ruído fica no contexto dele; só o resultado volta).

---

## Git workflow

### Inicialização (uma vez, no bootstrap)

Se o repo ainda não foi inicializado:
\`\`\`bash
git init
git branch -M main
# criar .gitignore (conteúdo abaixo) ANTES do primeiro commit
git add .gitignore README.md CLAUDE.md docs/
git commit -m "chore: bootstrap project structure and docs"
\`\`\`
NÃO commite código de produção no bootstrap — só estrutura, docs e \`.gitignore\`. NÃO conecte remoto nem faça push; o usuário fornece a URL e autoriza o push depois.

### Branch por feature + PR

- \`main\` não recebe commits diretos durante o desenvolvimento de uma etapa.
- Cada etapa do PLAN vira uma branch: \`git checkout -b feat/etapa-N-descricao\` (kebab-case).
- Tipos de branch: \`feat/\`, \`fix/\`, \`chore/\`, \`test/\`.
- Etapa concluída com suíte verde → merge na \`main\` local. NÃO faça push automático. Todo o trabalho fica local até o usuário revisar.
- Quando o usuário autorizar push: abrir PR para \`main\` com descrição referenciando a etapa do PLAN. NÃO fazer merge do PR sem autorização.

### Commits — Conventional Commits, um por ciclo red-green-refactor

Granularidade: **um commit por ciclo red-green-refactor completo**. Cada commit deixa a suíte verde (inclui teste + implementação + refactor juntos).

Formato (Conventional Commits, SEM escopo):
\`\`\`
<tipo>: <descrição imperativa curta>

[corpo opcional: o porquê, não o quê]
\`\`\`

Tipos: \`feat:\` (comportamento novo + teste), \`fix:\` (correção + teste que reproduz), \`test:\` (teste isolado, raro), \`refactor:\` (sem mudar comportamento), \`chore:\` (infra/config/deps), \`docs:\` (documentação).

Exemplos:
\`\`\`
feat: skip files already processed with same content hash
feat: validate dest_subdir rejects path traversal
fix: re-login on expired LightRAG token before failing
refactor: extract hash computation into scanner helper
chore: add apscheduler and httpx to backend deps
docs: update progress after etapa 1
\`\`\`

Regras:
- Mensagem em inglês, imperativa ("add", não "added").
- Primeira linha ≤ 72 caracteres.
- Um ciclo TDD = um commit. Não acumule comportamentos.
- NUNCA commit com suíte vermelha.
- NÃO incluir arquivos gerados, \`.env\`, ou artefatos de build.

### .gitignore (criar no bootstrap)

\`\`\`
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
*.egg-info/

# Env / secrets
.env
.env.*
!.env.example

# Node / frontend
node_modules/
frontend/dist/
*.local

# DB / dados locais
*.sqlite3
pgdata/

# IDE / OS
.vscode/
.idea/
.DS_Store
\`\`\`

---

## Stack

- Backend: FastAPI (Python 3.12), APScheduler, SQLAlchemy + Alembic, PostgreSQL
- Testes backend: pytest, pytest-asyncio, httpx (TestClient), banco de teste isolado
- Frontend: React + Vite + TypeScript
- Testes frontend: Vitest + React Testing Library
- Monorepo: \`backend/\` e \`frontend/\`

## Padrões de teste

- Backend: testes em \`backend/tests/\` espelhando \`app/\`. Banco de teste isolado. Cada teste independente, limpa seu estado.
- Frontend: testes co-localizados (\`Componente.test.tsx\`) ou em \`__tests__/\`.
- Integrações externas (Docling, LightRAG) MOCKADAS nos unitários. Testes de integração reais separados e marcados (\`@pytest.mark.integration\`), não rodam por padrão.

## Definition of Done por etapa

- [ ] Comportamentos da etapa cobertos por teste
- [ ] Suíte completa verde
- [ ] Sem código de produção não exercido por teste
- [ ] Migrations sobem e revertem (quando aplicável)
- [ ] Commits em Conventional Commits, um por ciclo TDD
- [ ] `docs/PROGRESS.md` atualizado
- [ ] Merge na `main` local feito
- [ ] `/clear` executado antes da próxima etapa
- [ ] SPEC atualizado se algum contrato mudou

## O que NÃO fazer

- NÃO usar watch reativo (inotify). Detecção é agendada + manual.
- NÃO implementar autenticação nesta fase (schema tem \`owner_id\`, mas sem login).
- NÃO usar o endpoint de upload do LightRAG; escrever \`.md\` direto na INPUT_DIR e chamar o scan.
- NÃO criar abstrações especulativas de multi-user além do \`owner_id\`.
- NÃO commitar direto na \`main\` durante uma etapa.
- NÃO fazer push ou merge de PR sem autorização do usuário.
- NÃO commitar com suíte vermelha.
- NÃO pular etapas nem antecipar features futuras.
