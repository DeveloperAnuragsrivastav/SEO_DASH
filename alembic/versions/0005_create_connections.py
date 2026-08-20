from __future__ import annotations
from typing import Optional

"""create connections table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from alembic import op

revision: str = "0005"
down_revision: Optional[str] = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE provider_type AS ENUM ('gsc', 'ga4', 'gbp', 'dataforseo')")
    provider_type = ENUM("gsc", "ga4", "gbp", "dataforseo", name='provider_type', create_type=False)

    op.execute("CREATE TYPE access_mode AS ENUM ('platform_shared', 'client_owned')")
    access_mode = ENUM("platform_shared", "client_owned", name='access_mode', create_type=False)

    op.execute("CREATE TYPE connection_status AS ENUM ('connected', 'error', 'expired', 'not_connected')")
    connection_status = ENUM(
        "connected", "error", "expired", "not_connected", name="connection_status", create_type=False
    )

    op.create_table(
        "connections",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", provider_type, nullable=False),
        sa.Column("access_mode", access_mode, nullable=False),
        sa.Column("credentials", JSONB(), nullable=True),
        sa.Column("property_id", sa.Text(), nullable=False),
        sa.Column("property_tz", sa.Text(), nullable=True),
        sa.Column("status", connection_status, nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
    )


def downgrade() -> None:
    op.drop_table("connections")
    op.execute("DROP TYPE IF EXISTS connection_status")
    op.execute("DROP TYPE IF EXISTS access_mode")
    op.execute("DROP TYPE IF EXISTS provider_type")
