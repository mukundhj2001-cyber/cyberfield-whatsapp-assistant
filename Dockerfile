# Cyberfield WhatsApp Assistant: one container, API + webhook + built dashboard.
FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DB_PATH=/data/assistant.db PORT=8000
WORKDIR /app
COPY requirements-prod.txt ./
RUN pip install -r requirements-prod.txt
COPY backend/ backend/
COPY --from=ui /ui/dist frontend/dist
RUN mkdir -p /data && useradd -r -u 10001 app && chown -R app /data /app
USER app
VOLUME ["/data"]
EXPOSE 8000
WORKDIR /app/backend
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
