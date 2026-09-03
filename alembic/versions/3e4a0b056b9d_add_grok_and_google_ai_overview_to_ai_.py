"""Add grok and google_ai_overview to ai_platform enum

Revision ID: 3e4a0b056b9d
Revises: 079510df09bc
Create Date: 2026-09-03 16:42:20.895322
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e4a0b056b9d'
down_revision: Union[str, None] = '079510df09bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Disable transaction block because ALTER TYPE ADD VALUE cannot run inside a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ai_platform ADD VALUE IF NOT EXISTS 'grok'")
        op.execute("ALTER TYPE ai_platform ADD VALUE IF NOT EXISTS 'google_ai_overview'")


def downgrade() -> None:
    # Postgres doesn't easily support dropping enum values.
    pass
