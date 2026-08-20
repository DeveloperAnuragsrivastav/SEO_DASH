from __future__ import annotations
from typing import Optional
import datetime

from sqlalchemy import Boolean, Date, Numeric, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProviderState(Base):
    """Global state for external API providers (e.g. pause flag)."""

    __tablename__ = "provider_states"

    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)


class DailyProviderCost(Base):
    """Materialized daily totals for cost guardrail aggregations."""

    __tablename__ = "daily_provider_costs"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    cost: Mapped[float] = mapped_column(Numeric, nullable=False, default=0.0)
