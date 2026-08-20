from __future__ import annotations
from typing import Optional

"""create provider_tasks table

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0008"
down_revision: Optional[str] = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE task_status AS ENUM ('pending', 'completed', 'failed')")
    task_status = ENUM("pending", "completed", "failed", name='task_status', create_type=False)

    op.create_table(
        "provider_tasks",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"]),
    )


def downgrade() -> None:
    op.drop_table("provider_tasks")
    op.execute("DROP TYPE IF EXISTS task_status")
