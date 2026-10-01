# ── 1. Frontend build ──────────────────────────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install -g npm@11 --no-audit --no-fund && npm ci --no-audit --no-fund
COPY frontend/ ./
RUN VITE_API_URL="" npm run build

# ── 2. Python dependencies ─────────────────────────────────────────────
FROM python:3.11-slim AS python-deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 3. Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    APP_ENV=production \
    MALLOC_ARENA_MAX=2
# MALLOC_ARENA_MAX: fewer malloc arenas, so memory freed after a PDF is not
# kept reserved per thread.

COPY --from=python-deps /opt/venv /opt/venv

# Only Chromium's headless shell (what PDFs need) and its system libraries.
RUN playwright install --with-deps --only-shell chromium \
    && apt-get install -y --no-install-recommends fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/* /tmp/*

# Only what runs: the API, its templates/static files and the migrations.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
# Railway sets $PORT. One worker: PDFs and report builds are memory-heavy,
# and a second worker would double the idle memory for a handful of users.
CMD ["sh", "-c", "alembic upgrade head && python -m app.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips '*' --no-access-log"]
