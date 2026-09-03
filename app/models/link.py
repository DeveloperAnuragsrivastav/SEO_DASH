from __future__ import annotations
from typing import Optional
import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, ForeignKey, Integer, Text, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import LinkStatus


class Link(Base):
    """Backlink entry — always manual in Phase 1. §11."""

    __tablename__ = "links"
    __table_args__ = (
        UniqueConstraint("client_id", "month", "url", "activity_type", name="uq_link_client_month_url_activity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    created_on: Mapped[date] = mapped_column(Date, nullable=False)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[LinkStatus] = mapped_column(
        Enum(LinkStatus, name="link_status", native_enum=True, create_constraint=False),
        nullable=False,
    )
    last_checked: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    dr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="links")
