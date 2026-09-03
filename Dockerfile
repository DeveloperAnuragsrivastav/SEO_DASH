# ── Frontend Builder Stage ─────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN VITE_API_URL="" npm run build

# ── Backend Builder Stage ──────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Remove dev dependencies (mypy, ruff, pytest)
RUN pip uninstall -y mypy ruff pytest pytest-cov 2>/dev/null || true

# Install Playwright Chromium browser
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# ── Runtime Stage ──────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (PostgreSQL client, Chromium deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    # Chromium runtime dependencies
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libwayland-client0 \
    fonts-liberation fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy Playwright browsers from builder
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=2

COPY . .
# Remove the raw frontend source code to save space
RUN rm -rf frontend/

# Copy the built React app from the frontend builder stage
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
