from __future__ import annotations
from typing import Optional
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MetricSource


class Metric(Base):
    """Generic metrics table (GSC, GA4, GBP, etc.). §11.

    The effective primary key uses COALESCE on nullable dimension columns:
        UNIQUE (client_id, provider, metric_key,
                COALESCE(dimension_key, ''), COALESCE(dimension_value, ''),
                captured_on)

    PostgreSQL doesn't support expression-based PRIMARY KEY constraints,
    so the uniqueness is enforced via a UNIQUE INDEX with COALESCE in the
    Alembic migration.  The ORM mapper uses the four non-nullable columns
    as its identity key; the DB index prevents the ambiguity this would
    otherwise allow.
    """

    __tablename__ = "metrics"

    # ORM identity columns (non-nullable subset of the full composite key).
    # The complete 6-column uniqueness is enforced by the DB index, not here.
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    metric_key: Mapped[str] = mapped_column(Text, primary_key=True)
    dimension_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True, primary_key=True)
    dimension_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, primary_key=True)
    captured_on: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    source: Mapped[MetricSource] = mapped_column(
        Enum(MetricSource, name="metric_source", native_enum=True, create_constraint=False),
        nullable=False,
    )

    # Relationships
    client = relationship("Client")
