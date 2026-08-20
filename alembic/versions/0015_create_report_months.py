from __future__ import annotations
from typing import Optional

"""create report_months table

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from alembic import op

revision: str = "0015"
down_revision: Optional[str] = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE report_status AS ENUM ('draft', 'review', 'published')")
    report_status = ENUM("draft", "review", "published", name='report_status', create_type=False)

    op.create_table(
        "report_months",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("status", report_status, nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("next_month_plan", JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        # Load-bearing unique constraint — §10's concurrency design depends on this
        sa.UniqueConstraint("client_id", "month", name="uq_report_months_client_month"),
    )


def downgrade() -> None:
    op.drop_table("report_months")
    op.execute("DROP TYPE IF EXISTS report_status")
