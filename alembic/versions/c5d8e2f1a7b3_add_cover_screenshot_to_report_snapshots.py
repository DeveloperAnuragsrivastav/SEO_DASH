"""Add a cover screenshot to report snapshots

Revision ID: c5d8e2f1a7b3
Revises: b304741a2b15
Create Date: 2026-09-11 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d8e2f1a7b3'
down_revision: Union[str, None] = 'b304741a2b15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both nullable: every existing report simply has no cover screenshot.
    op.add_column('report_snapshots', sa.Column('cover_image', sa.LargeBinary(), nullable=True))
    op.add_column('report_snapshots', sa.Column('cover_mime', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('report_snapshots', 'cover_mime')
    op.drop_column('report_snapshots', 'cover_image')
