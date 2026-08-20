from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RankingSource


class Ranking(Base):
    """Daily rank position per keyword. §11: composite PK (keyword_id, captured_on)."""

    __tablename__ = "rankings"

    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id"), primary_key=True
    )
    captured_on: Mapped[date] = mapped_column(Date, primary_key=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_overview_present: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    source: Mapped[RankingSource] = mapped_column(
        Enum(RankingSource, name="ranking_source", native_enum=True, create_constraint=False),
        nullable=False,
    )

    # Relationships
    keyword = relationship("Keyword", back_populates="rankings")
