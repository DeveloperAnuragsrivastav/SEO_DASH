from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import BusinessType, ClientStatus


class Client(Base):
    """A client managed by EZ Rankings. §11."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType, name="business_type", native_enum=True, create_constraint=False),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    package_keywords: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status", native_enum=True, create_constraint=False),
        nullable=False,
    )
    onboarded_at: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    account = relationship("Account", back_populates="clients")
    sections = relationship("ClientSection", back_populates="client")
    connections = relationship("Connection", back_populates="client")
    keywords = relationship("Keyword", back_populates="client")
    ai_prompts = relationship("AiPrompt", back_populates="client")
    ai_mentions = relationship("AiMention", back_populates="client")
    links = relationship("Link", back_populates="client")
    activities = relationship("Activity", back_populates="client")
    screenshots = relationship("Screenshot", back_populates="client")
    report_months = relationship("ReportMonth", back_populates="client")
    sync_runs = relationship("SyncRun", back_populates="client")
