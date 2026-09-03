"""Add file_data and mime_type to screenshots

Revision ID: b304741a2b15
Revises: 3e4a0b056b9d
Create Date: 2026-09-03 17:53:56.964125
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b304741a2b15'
down_revision: Union[str, None] = '3e4a0b056b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('screenshots', sa.Column('file_data', sa.LargeBinary(), nullable=True))
    op.add_column('screenshots', sa.Column('mime_type', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('screenshots', 'mime_type')
    op.drop_column('screenshots', 'file_data')
