from __future__ import annotations
import logging
import uuid
from datetime import date, datetime, timezone

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, RunReportRequest
from google.analytics.data_v1beta.types import Metric as GA4Metric
from google.api_core.exceptions import InvalidArgument, PermissionDenied
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, MetricSource, ProviderType, SyncStatus
from app.models.metric import Metric
from app.models.sync_run import SyncRun
from app.services.date_utils import calculate_previous_month
from app.services.google_auth import get_google_credentials

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _execute_ga4_query(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start_date: date,
    end_date: date,
    dimensions: list[str],
) -> list[dict]:
    if not property_id.startswith("properties/"):
        property_id = f"properties/{property_id}"

    request_dimensions = []
    if "date" in dimensions:
        request_dimensions.append(Dimension(name="date"))
        dimensions.remove("date")
        
    for dim in dimensions:
        request_dimensions.append(Dimension(name=dim))

    request_metrics = [
        GA4Metric(name="sessions"),
        GA4Metric(name="activeUsers"),
        GA4Metric(name="engagedSessions"),
        GA4Metric(name="conversions"),
        GA4Metric(name="purchaseRevenue"),
        GA4Metric(name="averageSessionDuration"),
        GA4Metric(name="addToCarts"),
    ]

    request = RunReportRequest(
        property=property_id,
        dimensions=request_dimensions,
        metrics=request_metrics,
        date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"))],
    )

    response = client.run_report(request=request)

    from typing import Any
    rows: list[dict[str, Any]] = []
    for row in response.rows:
        row_dict: dict[str, Any] = {}
        
        # Determine the primary dimension key (ignoring date if present)
        main_dims = [d.name for d in request_dimensions if d.name != "date"]
        
        for i, dim in enumerate(request_dimensions):
            if dim.name == "date":
                row_dict["date"] = row.dimension_values[i].value
            else:
                row_dict["dimension_key"] = dim.name
                row_dict["dimension_value"] = row.dimension_values[i].value

        if not main_dims:
            row_dict["dimension_key"] = None
            row_dict["dimension_value"] = None

        row_dict["sessions"] = float(row.metric_values[0].value)
        row_dict["activeUsers"] = float(row.metric_values[1].value)
        row_dict["engagedSessions"] = float(row.metric_values[2].value)
        row_dict["conversions"] = float(row.metric_values[3].value)
        row_dict["purchaseRevenue"] = float(row.metric_values[4].value)
        row_dict["averageSessionDuration"] = float(row.metric_values[5].value)
        row_dict["addToCarts"] = float(row.metric_values[6].value)

        rows.append(row_dict)

    return rows


def _pull_ga4_data_structured(property_id: str, start_date: date, end_date: date) -> dict:
    creds = get_google_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    # 1. True Totals (no dimensions)
    totals_rows = _execute_ga4_query(client, property_id, start_date, end_date, [])
    if totals_rows:
        r = totals_rows[0]
        totals = {
            "sessions": r.get("sessions", 0),
            "users": r.get("activeUsers", 0),
            "engaged_sessions": r.get("engagedSessions", 0),
            "conversions": r.get("conversions", 0),
            "revenue": r.get("purchaseRevenue", 0),
            "avg_session_duration": r.get("averageSessionDuration", 0),
            "add_to_carts": r.get("addToCarts", 0),
        }
    else:
        totals = {"sessions": 0, "users": 0, "engaged_sessions": 0, "conversions": 0, "revenue": 0, "avg_session_duration": 0, "add_to_carts": 0}

    # 2. Date Rows (for DB tracking)
    date_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["date"])

    # 3. Traffic Sources (sessionSource)
    source_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["sessionSource"])
    top_sources = sorted(source_rows, key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    sources_clean = [{"source": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in top_sources]

    # 4. Devices (deviceCategory)
    device_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["deviceCategory"])
    devices_clean = [{"device": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in device_rows]

    # 5. Top Pages (pagePath)
    page_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["pagePath"])
    top_pages = sorted(page_rows, key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    pages_clean = [{"page": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in top_pages]

    # 6. Organic Sessions (sessionDefaultChannelGroup)
    channel_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["sessionDefaultChannelGroup"])
    organic_sessions = 0
    for r in channel_rows:
        if r.get("dimension_value", "").lower() == "organic search":
            organic_sessions = r.get("sessions", 0)
            break
    totals["organic_sessions"] = organic_sessions

    # 7. Countries (country)
    country_rows = _execute_ga4_query(client, property_id, start_date, end_date, ["country"])
    top_countries = sorted(country_rows, key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    countries_clean = [{"country": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"]} for r in top_countries]

    # Date+Dimension rows for DB
    all_dim_rows = []
    all_dim_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["date", "sessionSource"]))
    all_dim_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["date", "deviceCategory"]))
    all_dim_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["date", "pagePath"]))
    # Countries are stored too, so a report built from saved data can show them.
    all_dim_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["date", "country"]))

    return {
        "totals": totals,
        "date_rows": date_rows,
        "dimension_rows": all_dim_rows,
        "traffic_sources": sources_clean,
        "devices": devices_clean,
        "top_pages": pages_clean,
        "countries": countries_clean,
    }


def pull_ga4_data(
    db: Session,
    connection_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    trigger_time: datetime | None = None,
) -> dict:
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")

    if conn.provider != ProviderType.ga4:
        raise ValueError(f"Cannot pull GA4 data for provider: {conn.provider}")

    if start_date is None or end_date is None:
        if trigger_time is None:
            trigger_time = datetime.now(timezone.utc)
        start_date, end_date = calculate_previous_month(conn.property_tz, trigger_time)

    assert start_date is not None
    assert end_date is not None

    started_at = datetime.now(timezone.utc)

    try:
        result = _pull_ga4_data_structured(conn.property_id, start_date, end_date)

        metrics_to_insert = []
        metric_key_map = {
            "sessions": "sessions",
            "activeUsers": "users",
            "engagedSessions": "engaged_sessions",
            "conversions": "conversions",
            "purchaseRevenue": "revenue",
            "averageSessionDuration": "avg_session_duration",
            "addToCarts": "add_to_carts",
        }

        all_raw_rows = result["date_rows"] + result["dimension_rows"]

        for row in all_raw_rows:
            # Safely handle missing date, default to start_date if GA4 returns a malformed row
            date_str = row.get("date")
            if date_str and len(date_str) == 8:
                captured_on = datetime.strptime(date_str, "%Y%m%d").date()
            else:
                captured_on = start_date

            for ga4_key, db_key in metric_key_map.items():
                val = row.get(ga4_key, 0)
                metrics_to_insert.append(
                    Metric(
                        client_id=conn.client_id,
                        provider="ga4",
                        metric_key=db_key,
                        dimension_key=row.get("dimension_key"),
                        dimension_value=row.get("dimension_value"),
                        captured_on=captured_on,
                        value=float(val),
                        source=MetricSource.api,
                    )
                )

        if metrics_to_insert:
            db.query(Metric).filter(
                Metric.client_id == conn.client_id,
                Metric.provider == "ga4",
                Metric.source == MetricSource.api,
                Metric.captured_on >= start_date,
                Metric.captured_on <= end_date,
            ).delete(synchronize_session=False)

            db.add_all(metrics_to_insert)

        sync_run = SyncRun(
            client_id=conn.client_id,
            provider="ga4",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status=SyncStatus.success,
            rows=len(metrics_to_insert),
        )
        db.add(sync_run)

        conn.last_verified_at = datetime.now(timezone.utc)
        conn.status = ConnectionStatus.connected
        conn.last_error = None

        db.commit()

        return {
            "totals": result["totals"],
            "traffic_sources": result["traffic_sources"],
            "devices": result["devices"],
            "top_pages": result["top_pages"],
            "countries": result["countries"],
            "rows_stored": len(metrics_to_insert),
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"GA4 pull failed for connection {connection_id}: {error_msg}")

        db.rollback()

        sync_run = SyncRun(
            client_id=conn.client_id,
            provider="ga4",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            status=SyncStatus.failed,
            error=error_msg,
        )

        conn.status = ConnectionStatus.error
        conn.last_error = error_msg

        db.add(sync_run)
        db.add(conn)
        db.commit()

        raise ValueError(f"GA4 pull failed: {error_msg}") from e

def get_ai_referrals(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
    # Simple placeholder returning AI referrals (e.g. chatgpt, claude, perplexity)
    from sqlalchemy import select, func
    from app.models.ga4_data import Ga4Data
    
    stmt = select(Ga4Data.dimension_value, func.sum(Ga4Data.sessions).label("sessions"))\
        .where(
            Ga4Data.client_id == client_id,
            Ga4Data.date >= start_date,
            Ga4Data.date <= end_date,
            Ga4Data.dimension_key == "sessionSource"
        )\
        .group_by(Ga4Data.dimension_value)
    
    rows = db.execute(stmt).all()
    
    ai_sources = ["chatgpt", "claude", "perplexity", "openai", "anthropic", "gemini"]
    
    results = []
    for row in rows:
        source = str(row[0] or "").lower()
        if any(ai in source for ai in ai_sources):
            results.append({
                "source": row[0],
                "sessions": int(row[1])
            })
            
    return sorted(results, key=lambda x: x["sessions"], reverse=True)
