from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Text, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Screenshot(Base):
    """Screenshot entry — always manual. §11."""

    __tablename__ = "screenshots"
    __table_args__ = (
        UniqueConstraint("client_id", "month", "keyword_id", name="uq_screenshot_client_month_kw"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    keyword_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id"), nullable=True
    )
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="screenshots")
    keyword = relationship("Keyword", back_populates="screenshots")
