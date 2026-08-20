from __future__ import annotations
from typing import Optional

"""create users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "0002"
down_revision: Optional[str] = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Native PG ENUM — not a CHECK constraint
    op.execute("CREATE TYPE user_role AS ENUM ('agency_admin', 'agency_staff')")
    user_role = ENUM("agency_admin", "agency_staff", name='user_role', create_type=False)

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),  # citext applied below
        sa.Column("role", user_role, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    # Cast the column to citext for case-insensitive uniqueness
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE citext USING email::citext")


def downgrade() -> None:
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
