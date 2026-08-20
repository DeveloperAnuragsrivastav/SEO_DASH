from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AccessMode, ConnectionStatus, ProviderType


class Connection(Base):
    """One row per data source per client. §11, §7."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    provider: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=True, create_constraint=False),
        nullable=False,
    )
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, name="access_mode", native_enum=True, create_constraint=False),
        nullable=False,
    )
    credentials: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    property_id: Mapped[str] = mapped_column(Text, nullable=False)
    property_tz: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status", native_enum=True, create_constraint=False),
        nullable=False,
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="connections")
    provider_tasks = relationship("ProviderTask", back_populates="connection")
