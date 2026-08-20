from __future__ import annotations
from typing import Optional

"""create ai_mentions table

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from alembic import op

revision: str = "0010"
down_revision: Optional[str] = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE ai_platform AS ENUM ('chatgpt', 'claude', 'gemini', 'perplexity')")
    ai_platform = ENUM("chatgpt", "claude", "gemini", "perplexity", name='ai_platform', create_type=False)

    op.execute("CREATE TYPE ai_mention_source AS ENUM ('llm_responses_custom', 'manual')")
    ai_mention_source = ENUM("llm_responses_custom", "manual", name='ai_mention_source', create_type=False)

    op.create_table(
        "ai_mentions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_id", UUID(as_uuid=True), nullable=True),
        sa.Column("platform", ai_platform, nullable=False),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("mentioned", sa.Boolean(), nullable=True),
        sa.Column("cited_pages", JSONB(), nullable=True),
        sa.Column("source", ai_mention_source, nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["prompt_id"], ["ai_prompts.id"]),
    )


def downgrade() -> None:
    op.drop_table("ai_mentions")
    op.execute("DROP TYPE IF EXISTS ai_mention_source")
    op.execute("DROP TYPE IF EXISTS ai_platform")
