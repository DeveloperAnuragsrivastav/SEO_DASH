"""Month-on-month sheets: the final, published figures of every client

Revision ID: e4b9d2a6c1f8
Revises: d7a1c3e9b2f4
Create Date: 2026-09-30 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e4b9d2a6c1f8'
down_revision: Union[str, None] = 'd7a1c3e9b2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sheet_cells',
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sheet', sa.Text(), nullable=False),
        sa.Column('row_key', sa.Text(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('grp', sa.Text(), server_default='', nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('ordinal', sa.Integer(), server_default='0', nullable=False),
        sa.Column('value', sa.Numeric(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('edited', sa.Boolean(), server_default='false', nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['report_snapshots.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('client_id', 'sheet', 'row_key', 'month'),
    )


def downgrade() -> None:
    op.drop_table('sheet_cells')
