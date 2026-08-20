from __future__ import annotations
from typing import Optional

"""create metrics table

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0011"
down_revision: Optional[str] = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE metric_source AS ENUM ('api', 'manual')")
    metric_source = ENUM("api", "manual", name='metric_source', create_type=False)

    # No formal PRIMARY KEY — the effective PK uses COALESCE on nullable
    # dimension columns, which PG doesn't support in a PK constraint.
    # Uniqueness enforced via the index below.
    op.create_table(
        "metrics",
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("dimension_key", sa.Text(), nullable=True),
        sa.Column("dimension_value", sa.Text(), nullable=True),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("source", metric_source, nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )

    # Composite PRIMARY KEY equivalent with COALESCE — per architecture §11.
    # This is the de facto PK; nullable columns can't participate in a plain
    # PG PRIMARY KEY, so COALESCE maps NULLs to '' for uniqueness purposes.
    op.execute("""
        CREATE UNIQUE INDEX uq_metrics_pk ON metrics (
            client_id, provider, metric_key,
            COALESCE(dimension_key, ''),
            COALESCE(dimension_value, ''),
            captured_on
        )
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_metrics_pk")
    op.drop_table("metrics")
    op.execute("DROP TYPE IF EXISTS metric_source")
