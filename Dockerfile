# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production image
FROM python:3.12-slim
WORKDIR /app

COPY backend/pyproject.toml ./
RUN python3 -c "import tomllib,subprocess,sys; f=open('pyproject.toml','rb'); d=tomllib.load(f); f.close(); subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir']+d['project']['dependencies'],check=True)"

COPY backend/ ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -c 'from app.config import Settings; from app.database import get_engine, get_session_factory; from app.seed import seed_from_config; s=Settings(); e=get_engine(s.database_url); f=get_session_factory(e); db=f(); seed_from_config(db); db.close(); e.dispose()' && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
