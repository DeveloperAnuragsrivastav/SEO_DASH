"""Migration tests — verify every table exists with correct columns and constraints.

These tests run against a real Postgres instance (via conftest.py's Alembic
migration fixture), not SQLite, so PG-specific features like ENUM types,
jsonb, uuid defaults, citext, and COALESCE-based unique indexes are
genuinely tested.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

# ── Helpers ────────────────────────────────────────────────────────────

def _table_columns(db_session: Session, table: str) -> set[str]:
    """Return column names for a table."""
    inspector = inspect(db_session.bind)
    return {c["name"] for c in inspector.get_columns(table)}


def _table_exists(db_session: Session, table: str) -> bool:
    inspector = inspect(db_session.bind)
    return table in inspector.get_table_names()


# ── Table existence tests ─────────────────────────────────────────────

EXPECTED_TABLES = [
    "accounts", "users", "clients", "client_sections", "connections",
    "keywords", "rankings", "provider_tasks", "ai_prompts", "ai_mentions",
    "metrics", "links", "activities", "screenshots", "report_months",
    "sync_runs",
]


@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_table_exists(db_session: Session, table: str) -> None:
    assert _table_exists(db_session, table), f"Table '{table}' not found"


# ── Column existence tests ────────────────────────────────────────────

def test_accounts_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "accounts")
    assert {"id", "name", "created_at"} <= cols


def test_users_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "users")
    assert {"id", "account_id", "email", "role", "last_login_at"} <= cols


def test_clients_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "clients")
    assert {"id", "account_id", "name", "domain", "logo_url", "business_type",
            "locale", "package_keywords", "status", "onboarded_at"} <= cols


def test_client_sections_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "client_sections")
    assert {"client_id", "section_key", "enabled"} <= cols


def test_connections_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "connections")
    assert {"id", "client_id", "provider", "access_mode", "credentials",
            "property_id", "property_tz", "status", "last_verified_at",
            "last_sync_at", "last_error"} <= cols


def test_keywords_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "keywords")
    assert {"id", "client_id", "term", "group_tag", "target_url",
            "search_volume", "initial_rank", "is_active", "added_at"} <= cols


def test_rankings_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "rankings")
    assert {"keyword_id", "captured_on", "position", "url",
            "ai_overview_present", "source"} <= cols


def test_provider_tasks_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "provider_tasks")
    assert {"id", "connection_id", "task_id", "tag", "status",
            "submitted_at", "completed_at", "cost"} <= cols


def test_ai_prompts_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "ai_prompts")
    assert {"id", "client_id", "prompt_text", "is_active", "added_at"} <= cols


def test_ai_mentions_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "ai_mentions")
    assert {"id", "client_id", "prompt_id", "platform", "captured_on",
            "mentioned", "cited_pages", "source", "raw_response"} <= cols


def test_metrics_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "metrics")
    assert {"client_id", "provider", "metric_key", "dimension_key",
            "dimension_value", "captured_on", "value", "source"} <= cols


def test_links_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "links")
    assert {"id", "client_id", "created_on", "activity_type", "domain",
            "url", "status", "last_checked", "dr"} <= cols


def test_activities_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "activities")
    assert {"id", "client_id", "month", "activity_type", "count", "notes"} <= cols


def test_screenshots_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "screenshots")
    assert {"id", "client_id", "month", "keyword_id", "file_url", "caption"} <= cols


def test_report_months_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "report_months")
    assert {"id", "client_id", "month", "status", "snapshot", "narrative",
            "next_month_plan", "generated_at", "published_at", "published_by"} <= cols


def test_sync_runs_columns(db_session: Session) -> None:
    cols = _table_columns(db_session, "sync_runs")
    assert {"id", "client_id", "provider", "started_at", "finished_at",
            "status", "rows", "error"} <= cols


# ── Constraint tests ──────────────────────────────────────────────────

def test_report_months_unique_constraint_rejects_duplicate(db_session: Session) -> None:
    """Explicitly test that UNIQUE(client_id, month) actually rejects a
    duplicate insert — this constraint is load-bearing for §10's
    concurrency design."""
    # First, insert an account and client to satisfy FKs
    account_id = uuid.uuid4()
    client_id = uuid.uuid4()
    month = date(2026, 7, 1)

    db_session.execute(text(
        "INSERT INTO accounts (id, name) VALUES (:id, :name)"
    ), {"id": str(account_id), "name": "Test Account"})
    db_session.execute(text(
        "INSERT INTO clients (id, account_id, name, domain, business_type, "
        "locale, package_keywords, status, onboarded_at) "
        "VALUES (:id, :aid, :name, :domain, 'ecommerce', 'en', 10, 'active', :date)"
    ), {"id": str(client_id), "aid": str(account_id), "name": "Test Client",
        "domain": "test.com", "date": date(2026, 1, 1)})

    # First insert — should succeed
    db_session.execute(text(
        "INSERT INTO report_months (client_id, month, status, snapshot) "
        "VALUES (:cid, :month, 'draft', :snapshot)"
    ), {"cid": str(client_id), "month": month, "snapshot": "{}"})
    db_session.flush()

    # Second insert with same client_id + month — must fail
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match="uq_report_months_client_month"):
        db_session.execute(text(
            "INSERT INTO report_months (client_id, month, status, snapshot) "
            "VALUES (:cid, :month, 'draft', :snapshot)"
        ), {"cid": str(client_id), "month": month, "snapshot": "{}"})
        db_session.flush()


def test_rankings_composite_pk(db_session: Session) -> None:
    """Verify rankings has a composite PK (keyword_id, captured_on)."""
    inspector = inspect(db_session.bind)
    pk = inspector.get_pk_constraint("rankings")
    assert set(pk["constrained_columns"]) == {"keyword_id", "captured_on"}


def test_client_sections_composite_pk(db_session: Session) -> None:
    """Verify client_sections has a composite PK (client_id, section_key)."""
    inspector = inspect(db_session.bind)
    pk = inspector.get_pk_constraint("client_sections")
    assert set(pk["constrained_columns"]) == {"client_id", "section_key"}


def test_metrics_coalesce_unique_index_exists(db_session: Session) -> None:
    """Verify the COALESCE-based unique index exists on metrics."""
    inspector = inspect(db_session.bind)
    indexes = inspector.get_indexes("metrics")
    uq_index = [i for i in indexes if i["name"] == "uq_metrics_pk"]
    assert len(uq_index) == 1, "uq_metrics_pk index not found"
    assert uq_index[0]["unique"] is True


# ── ENUM type tests ───────────────────────────────────────────────────

EXPECTED_ENUMS = [
    "user_role", "business_type", "client_status", "provider_type",
    "access_mode", "connection_status", "ranking_source", "task_status",
    "ai_platform", "ai_mention_source", "metric_source", "link_status",
    "report_status", "sync_status",
]


@pytest.mark.parametrize("enum_name", EXPECTED_ENUMS)
def test_pg_enum_type_exists(db_session: Session, enum_name: str) -> None:
    """Verify each enum is a real PG ENUM type, not a CHECK constraint."""
    result = db_session.execute(
        text("SELECT 1 FROM pg_type WHERE typname = :name AND typtype = 'e'"),
        {"name": enum_name},
    )
    assert result.fetchone() is not None, f"PG ENUM type '{enum_name}' not found"
