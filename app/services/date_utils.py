from __future__ import annotations
"""Shared date utilities for timezone-aware month-boundary computation."""

from calendar import monthrange
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def calculate_previous_month(
    property_tz: str | None,
    trigger_time: datetime,
) -> tuple[date, date]:
    """Calculate the previous month's start and end date in the property's timezone.

    If property_tz is not set, defaults to timezone.utc.
    Used by GA4 and GBP services for month-boundary computation per architecture §10/§14.
    """
    tz = ZoneInfo(property_tz) if property_tz else timezone.utc
    local_time = trigger_time.astimezone(tz)

    if local_time.month == 1:
        prev_month = 12
        prev_year = local_time.year - 1
    else:
        prev_month = local_time.month - 1
        prev_year = local_time.year

    _, last_day = monthrange(prev_year, prev_month)

    start_date = date(prev_year, prev_month, 1)
    end_date = date(prev_year, prev_month, last_day)
    return start_date, end_date
