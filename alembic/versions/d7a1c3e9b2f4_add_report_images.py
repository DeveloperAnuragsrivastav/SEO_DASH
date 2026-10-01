"""Add per-report screenshots (e.g. the Google Business Profile captures)

Revision ID: d7a1c3e9b2f4
Revises: c5d8e2f1a7b3
Create Date: 2026-09-29 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd7a1c3e9b2f4'
down_revision: Union[str, None] = 'c5d8e2f1a7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'report_images',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section', sa.Text(), nullable=False),
        sa.Column('slot', sa.Integer(), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('mime', sa.Text(), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['report_snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_id', 'section', 'slot', name='uq_report_images_slot'),
    )
    op.create_index('ix_report_images_report_id', 'report_images', ['report_id'])


def downgrade() -> None:
    op.drop_index('ix_report_images_report_id', table_name='report_images')
    op.drop_table('report_images')
