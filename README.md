# EZ Rankings SEO Dashboard

Internal SEO reporting platform for EZ Rankings — automates data collection
and report assembly so the human review step is informed by clean, sourced
data instead of manual spreadsheet-pulling.

**Phase:** Foundation (infrastructure only — no connectors, no business logic,
no routes beyond health checks).

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL (Supabase-hosted)
- **Queue:** Celery + Redis (infrastructure wired, no tasks yet)
- **Hosting:** Railway / Render (Docker-supported)

## Local development

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.11+ and a virtualenv for running linters/tests
  directly

### Bring-up (Docker)

```bash
# Clone and enter the project
cd seo_dahboard

# Copy env template
cp .env.example .env

# Start all services (Postgres + Redis + app + Celery worker)
docker-compose up --build

# The app is now running at http://localhost:8000
# Migrations run automatically on startup
```

### Verify it's working

```bash
# Liveness — process is up
curl http://localhost:8000/health/live
# → {"status":"ok"}

# Readiness — Postgres connectivity confirmed
curl http://localhost:8000/health/ready
# → {"status":"ok","database":"connected"}
```

### Without Docker (local Python)

```bash
# Create and activate a virtualenv
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Ensure Postgres and Redis are running locally, then:
cp .env.example .env
# Edit .env with your local Postgres/Redis URLs

# Run migrations
alembic upgrade head

# Start the app
uvicorn app.main:app --reload

# Run tests (needs a running Postgres instance)
pytest -v
```

### Running tests

Tests require a real Postgres instance (not SQLite) to exercise PG-specific
features (ENUM types, jsonb, uuid defaults, citext, COALESCE indexes).

```bash
# With Docker already running:
docker-compose exec app pytest -v

# Or with local Python + local/Docker Postgres:
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ez_rankings_test \
  pytest -v
```

### Linting and type-checking

```bash
ruff check .
mypy app/ --ignore-missing-imports
```

## Project structure

```
├── app/
│   ├── main.py            # FastAPI application
│   ├── config.py           # Settings from .env
│   ├── database.py         # SQLAlchemy engine/session/Base
│   ├── celery_app.py       # Celery instance (no tasks yet)
│   ├── models/             # 16 SQLAlchemy models (§11)
│   └── routes/
│       └── health.py       # /health/live + /health/ready
├── alembic/
│   └── versions/           # 16 migrations, one per table
├── tests/
│   ├── conftest.py         # Real-Postgres fixtures
│   ├── test_migrations.py  # Table/column/constraint tests
│   └── test_health.py      # Health endpoint tests
├── docker-compose.yml      # Local dev stack
├── Dockerfile
├── .github/workflows/ci.yml
└── requirements.txt
```

## CI/CD

- **Every push:** ruff lint → mypy type-check → alembic migrate → pytest
- **Merge to main:** auto-deploy to staging (Railway)
- **Production:** manual trigger only (`workflow_dispatch`)
