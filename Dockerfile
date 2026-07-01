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
COPY start.sh /start.sh
RUN chmod +x /start.sh

ENV PYTHONPATH=/app
EXPOSE 8000
EXPOSE 9700

CMD ["/start.sh"]
