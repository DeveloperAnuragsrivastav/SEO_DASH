from __future__ import annotations
"""Health-check route tests."""

import os

from fastapi.testclient import TestClient


def _get_test_client() -> TestClient:
    """Build a TestClient with DATABASE_URL pointing at the test DB."""
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/ez_rankings_test",
    )
    os.environ["DATABASE_URL"] = test_db_url

    # Reimport to pick up the overridden env var.
    # The engine is created at module level in app.database, so we need
    # to patch it after import.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import get_db
    from app.main import app

    engine = create_engine(test_db_url, pool_pre_ping=True)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def _override_get_db():  # type: ignore[no-untyped-def]
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_liveness() -> None:
    """GET /health/live — confirms the process is up."""
    client = _get_test_client()
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_readiness(test_engine) -> None:  # type: ignore[no-untyped-def]
    """GET /health/ready — confirms Postgres connectivity via actual query."""
    client = _get_test_client()
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
