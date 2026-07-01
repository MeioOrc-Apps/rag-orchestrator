#!/bin/sh
set -e

alembic upgrade head

python -c "
from app.config import Settings
from app.database import get_engine, get_session_factory
from app.seed import seed_from_config
s = Settings()
e = get_engine(s.database_url)
f = get_session_factory(e)
db = f()
seed_from_config(db)
db.close()
e.dispose()
"

uvicorn app.mcp_server:mcp_app --host 0.0.0.0 --port "${MCP_PORT:-9700}" &

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
