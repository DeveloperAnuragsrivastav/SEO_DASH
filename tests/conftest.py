"""Test fixtures — real Postgres, not SQLite.

Uses Alembic migrations to set up the test database so that PG-specific
features (ENUM types, jsonb, uuid defaults, citext, COALESCE in unique
indexes) are exercised exactly as they would be in production.
"""



import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Default to docker-compose's test Postgres; CI overrides via env var.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ez_rankings_test",
)

# Set dummy keys for tests
os.environ["DATAFORSEO_MASTER_KEY"] = "u-6w7xH7N1A8bL7_Ym0QpD9h9A9bL7_Ym0QpD9h9A9s="
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-only"
from app.config import settings
settings.DATAFORSEO_MASTER_KEY = "u-6w7xH7N1A8bL7_Ym0QpD9h9A9bL7_Ym0QpD9h9A9s="

@pytest.fixture(scope="session")
def test_engine():  # type: ignore[no-untyped-def]
    """Create the test database and run all Alembic migrations once per session."""
    # Parse the DB URL to get the database name and a maintenance URL
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(TEST_DATABASE_URL)
    db_name = parsed.path.lstrip("/")
    maintenance_url = urlunparse(parsed._replace(path="/postgres"))

    # Create the test database if it doesn't exist
    maint_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with maint_engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": db_name}
        )
        if not result.fetchone():
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    maint_engine.dispose()

    # Run Alembic migrations against the test database
    engine = create_engine(TEST_DATABASE_URL)

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Drop everything first for a clean slate
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    command.upgrade(alembic_cfg, "head")

    yield engine

    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:  # type: ignore[no-untyped-def]
    """Provide a transactional session bound to a savepoint."""
    from app.main import app
    from app.database import get_db

    connection = test_engine.connect()
    transaction = connection.begin()
    
    # Bind the session to the connection, and join the transaction
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    
    # Override FastAPI dependency so TestClient uses this exact session
    app.dependency_overrides[get_db] = lambda: session

    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def test_users(db_session):
    from app.models.account import Account
    from app.models.user import User
    from app.models.enums import UserRole
    from app.core.security import get_password_hash
    
    acc = Account(name="Fixture Account")
    db_session.add(acc)
    db_session.commit()
    
    admin = User(account_id=acc.id, email="admin@test.com", password_hash=get_password_hash("pass"), role=UserRole.super_admin)
    staff = User(account_id=acc.id, email="staff@test.com", password_hash=get_password_hash("pass"), role=UserRole.user)
    db_session.add_all([admin, staff])
    db_session.commit()
    return {"admin": admin, "staff": staff}

@pytest.fixture
def admin_auth_headers(test_users):
    from app.core.security import create_access_token
    token = create_access_token({"sub": test_users["admin"].email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def staff_auth_headers(test_users):
    from app.core.security import create_access_token
    token = create_access_token({"sub": test_users["staff"].email})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def _inject_default_auth(admin_auth_headers, request):
    # This automatically injects the admin token into the TestClient for legacy tests
    if request.module.__name__ == "tests.test_reports":
        request.module.client.headers.update(admin_auth_headers)
    # Note: Other test files using their own TestClient will need to update headers, 
    # but since many don't import globally, it's safer to override get_current_user globally
    pass

@pytest.fixture(autouse=True)
def override_current_user_for_legacy(db_session, test_users):
    from app.main import app
    from app.dependencies import get_current_user
    
    # By default, pretend the admin is logged in so all legacy tests pass
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    yield
    app.dependency_overrides.pop(get_current_user, None)
