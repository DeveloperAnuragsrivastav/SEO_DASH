from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClientSection(Base):
    """Per-client section toggles. §11: composite PK (client_id, section_key)."""

    __tablename__ = "client_sections"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), primary_key=True
    )
    section_key: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="sections")
