from __future__ import annotations
from typing import Optional

"""create sync_runs table

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0016"
down_revision: Optional[str] = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE sync_status AS ENUM ('success', 'partial', 'failed')")
    sync_status = ENUM("success", "partial", "failed", name='sync_status', create_type=False)

    op.create_table(
        "sync_runs",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )


def downgrade() -> None:
    op.drop_table("sync_runs")
    op.execute("DROP TYPE IF EXISTS sync_status")
