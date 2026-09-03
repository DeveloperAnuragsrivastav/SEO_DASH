from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Text, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AiMentionSource, AiPlatform


class AiMention(Base):
    """AI-visibility result per platform per prompt. §11, §6."""

    __tablename__ = "ai_mentions"
    __table_args__ = (
        UniqueConstraint("client_id", "month", "prompt_id", "platform", name="uq_aimention_client_month_prompt_plat"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_prompts.id"), nullable=True
    )
    platform: Mapped[AiPlatform] = mapped_column(
        Enum(AiPlatform, name="ai_platform", native_enum=True, create_constraint=False),
        nullable=False,
    )
    captured_on: Mapped[date] = mapped_column(Date, nullable=False)
    mentioned: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cited_pages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    source: Mapped[AiMentionSource] = mapped_column(
        Enum(AiMentionSource, name="ai_mention_source", native_enum=True, create_constraint=False),
        nullable=False,
    )
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="ai_mentions")
    prompt = relationship("AiPrompt", back_populates="mentions")
