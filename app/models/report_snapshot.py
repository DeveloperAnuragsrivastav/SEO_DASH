from __future__ import annotations
from typing import Optional
import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReportStatus


class ReportSnapshot(Base):
    """Rolling snapshot report per client. §11, §10.

    UNIQUE(client_id, start_date, end_date) is load-bearing — §10's concurrency design
    depends on this being a real DB constraint.
    """

    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint("client_id", "start_date", "end_date", name="uq_report_snapshots_client_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", native_enum=True, create_constraint=False),
        nullable=False,
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_month_plan: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    client = relationship("Client", back_populates="report_snapshots")
    publisher = relationship("User", back_populates="published_reports")
