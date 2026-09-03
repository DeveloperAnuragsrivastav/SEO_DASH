from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AiPrompt(Base):
    """Tracked prompts per client for AI-visibility. §11, §6."""

    __tablename__ = "ai_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    added_at: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="ai_prompts")
    mentions = relationship("AiMention", back_populates="prompt")
