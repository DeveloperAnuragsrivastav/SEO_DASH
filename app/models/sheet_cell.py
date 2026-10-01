from __future__ import annotations
from typing import Optional
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SheetCell(Base):
    """One figure of a client's month-on-month sheet.

    The sheets (Search Console, Analytics, Keywords, …) hold only final data:
    a month's cells are written when that month's report is published, and
    after that only a super admin may correct them. A draft never writes here.
    """

    __tablename__ = "sheet_cells"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True
    )
    sheet: Mapped[str] = mapped_column(Text, primary_key=True)
    row_key: Mapped[str] = mapped_column(Text, primary_key=True)
    # The first day of the month the figure belongs to.
    month: Mapped[date] = mapped_column(Date, primary_key=True)

    # The row's group ("Leads", "Channels", …) and name as the sheet prints them.
    grp: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    label: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    value: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set when a super admin changed the figure after publishing.
    edited: Mapped[bool] = mapped_column(nullable=False, server_default="false")
