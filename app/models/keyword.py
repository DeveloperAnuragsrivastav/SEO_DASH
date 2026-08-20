from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Keyword(Base):
    """Tracked keyword for a client. §11."""

    __tablename__ = "keywords"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    group_tag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    initial_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    added_at: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="keywords")
    rankings = relationship("Ranking", back_populates="keyword")
    screenshots = relationship("Screenshot", back_populates="keyword")
