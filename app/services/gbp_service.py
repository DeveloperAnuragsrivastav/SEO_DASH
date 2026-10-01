from __future__ import annotations
"""GBP (Google Business Profile) data-pulling service.

Uses the Business Profile Performance API's fetchMultiDailyMetricsTimeSeries
batch endpoint to pull all metrics in a single call per date range.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType
from app.services.date_utils import calculate_previous_month
from app.services.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

# Every daily metric we pull, mapped from the API enum to our DB metric_key
GBP_METRIC_MAP: dict[str, str] = {
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "impressions_desktop_maps",
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH": "impressions_desktop_search",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "impressions_mobile_maps",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": "impressions_mobile_search",
    "CALL_CLICKS": "calls",
    "BUSINESS_DIRECTION_REQUESTS": "direction_requests",
    "WEBSITE_CLICKS": "website_clicks",
    "BUSINESS_BOOKINGS": "bookings",
    # Messages sent through the profile. Reported alongside calls because a
    # chat is the same intent arriving by a different door.
    "BUSINESS_CONVERSATIONS": "chat_clicks",
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _fetch_gbp_metrics(
    location_name: str,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Fetch all GBP daily metrics via fetchMultiDailyMetricsTimeSeries.

    Returns a flat list of dicts with keys: date, metric_key, value.
    """
    creds = get_google_credentials()
    service = build(
        "businessprofileperformance", "v1",
        credentials=creds, cache_discovery=False,
    )

    if not location_name.startswith("locations/"):
        location_name = f"locations/{location_name}"

    response = service.locations().fetchMultiDailyMetricsTimeSeries(
        location=location_name,
        dailyMetrics=list(GBP_METRIC_MAP.keys()),
        dailyRange_startDate_year=start_date.year,
        dailyRange_startDate_month=start_date.month,
        dailyRange_startDate_day=start_date.day,
        dailyRange_endDate_year=end_date.year,
        dailyRange_endDate_month=end_date.month,
        dailyRange_endDate_day=end_date.day,
    ).execute()

    rows: list[dict[str, Any]] = []

    # response structure:
    # { "multiDailyMetricTimeSeries": [ { "dailyMetric": "...", "timeSeries": { "datedValues": [...] } } ] }
    for series in response.get("multiDailyMetricTimeSeries", []):
        api_metric = series.get("dailyMetricTimeSeries", {}).get("dailyMetric", "")
        db_key = GBP_METRIC_MAP.get(api_metric)
        if not db_key:
            continue

        time_series = series.get("dailyMetricTimeSeries", {}).get("timeSeries", {})
        for dv in time_series.get("datedValues", []):
            d = dv.get("date", {})
            captured_on = date(d["year"], d["month"], d["day"])
            value = int(dv.get("value", 0))
            rows.append({
                "date": captured_on,
                "metric_key": db_key,
                "value": value,
            })

    return rows


def pull_gbp_data(
    db: Session,
    connection_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    trigger_time: datetime | None = None,
) -> list[tuple]:
    """Pull Business Profile figures for a window. Nothing is stored: the
    daily rows come back for the report being built to keep.

    Rows are (provider, day, metric_key, dimension_key, dimension_value, value, source).
    """
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")
    if conn.provider != ProviderType.gbp:
        raise ValueError(f"Cannot pull GBP data for provider: {conn.provider}")

    if start_date is None or end_date is None:
        if trigger_time is None:
            trigger_time = datetime.now(timezone.utc)
        start_date, end_date = calculate_previous_month(conn.property_tz, trigger_time)
    assert start_date is not None and end_date is not None

    try:
        raw_rows = _fetch_gbp_metrics(conn.property_id, start_date, end_date)
    except Exception as e:
        error_msg = str(e)
        if isinstance(e, HttpError):
            error_msg = getattr(e, "reason", str(e))
        logger.error("GBP pull failed for connection %s: %s", connection_id, error_msg)
        db.rollback()
        conn.status = ConnectionStatus.error
        conn.last_error = error_msg
        db.commit()
        raise ValueError(f"GBP pull failed: {error_msg}") from e

    conn.last_verified_at = datetime.now(timezone.utc)
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.status = ConnectionStatus.connected
    conn.last_error = None
    db.commit()
    return [("gbp", r["date"], r["metric_key"], None, None, float(r["value"]), "api") for r in raw_rows]
