from __future__ import annotations
from typing import Optional

"""create clients table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0003"
down_revision: Optional[str] = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE business_type AS ENUM ('ecommerce', 'leadgen', 'local', 'saas')")
    business_type = ENUM("ecommerce", "leadgen", "local", "saas", name='business_type', create_type=False)

    op.execute("CREATE TYPE client_status AS ENUM ('active', 'paused', 'churned')")
    client_status = ENUM("active", "paused", "churned", name='client_status', create_type=False)

    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("business_type", business_type, nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("package_keywords", sa.Integer(), nullable=False),
        sa.Column("status", client_status, nullable=False),
        sa.Column("onboarded_at", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
    )


def downgrade() -> None:
    op.drop_table("clients")
    op.execute("DROP TYPE IF EXISTS client_status")
    op.execute("DROP TYPE IF EXISTS business_type")
