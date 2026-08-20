from __future__ import annotations
from typing import Optional

"""create rankings table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0007"
down_revision: Optional[str] = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE ranking_source AS ENUM ('api', 'manual')")
    ranking_source = ENUM("api", "manual", name='ranking_source', create_type=False)

    op.create_table(
        "rankings",
        sa.Column("keyword_id", UUID(as_uuid=True), nullable=False),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("ai_overview_present", sa.Boolean(), nullable=True),
        sa.Column("source", ranking_source, nullable=False),
        sa.PrimaryKeyConstraint("keyword_id", "captured_on"),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"]),
    )


def downgrade() -> None:
    op.drop_table("rankings")
    op.execute("DROP TYPE IF EXISTS ranking_source")
