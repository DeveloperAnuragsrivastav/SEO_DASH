from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportImage(Base):
    """A screenshot that belongs to one report, in a numbered slot of one of
    its slides (e.g. the five Google Business Profile captures).

    Kept per report, like the cover screenshot, so each month's report shows
    that month's captures and publishing one never changes another.
    """

    __tablename__ = "report_images"
    __table_args__ = (
        UniqueConstraint("report_id", "section", "slot", name="uq_report_images_slot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    # Deferred: the bytes load only when the report is rendered or the image served.
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
