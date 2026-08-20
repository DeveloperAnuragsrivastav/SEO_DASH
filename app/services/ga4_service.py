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

    request_dimensions = [Dimension(name="date")]
    for dim in dimensions:
        request_dimensions.append(Dimension(name=dim))

    request_metrics = [
        GA4Metric(name="sessions"),
        GA4Metric(name="activeUsers"),
        GA4Metric(name="engagedSessions"),
        GA4Metric(name="conversions"),
        GA4Metric(name="purchaseRevenue"),
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
        row_dict["date"] = row.dimension_values[0].value

        if dimensions:
            row_dict["dimension_key"] = dimensions[0]
            row_dict["dimension_value"] = row.dimension_values[1].value
        else:
            row_dict["dimension_key"] = None
            row_dict["dimension_value"] = None

        row_dict["sessions"] = row.metric_values[0].value
        row_dict["activeUsers"] = row.metric_values[1].value
        row_dict["engagedSessions"] = row.metric_values[2].value
        row_dict["conversions"] = row.metric_values[3].value
        row_dict["purchaseRevenue"] = row.metric_values[4].value

        rows.append(row_dict)

    return rows


def _pull_ga4_data_all_dimensions(property_id: str, start_date: date, end_date: date) -> list[dict]:
    creds = get_google_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    all_rows = []

    all_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, []))
    all_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["sessionDefaultChannelGroup"]))
    all_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["deviceCategory"]))
    all_rows.extend(_execute_ga4_query(client, property_id, start_date, end_date, ["country"]))

    return all_rows


def pull_ga4_data(
    db: Session,
    connection_id: uuid.UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    trigger_time: Optional[datetime] = None,
) -> int:
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
        raw_rows = _pull_ga4_data_all_dimensions(conn.property_id, start_date, end_date)

        metrics_to_insert = []
        metric_key_map = {
            "sessions": "sessions",
            "activeUsers": "users",
            "engagedSessions": "engaged_sessions",
            "conversions": "conversions",
            "purchaseRevenue": "revenue",
        }

        for row in raw_rows:
            captured_on = datetime.strptime(row["date"], "%Y%m%d").date()

            for ga4_key, db_key in metric_key_map.items():
                val = row.get(ga4_key, 0)
                metrics_to_insert.append(
                    Metric(
                        client_id=conn.client_id,
                        provider="ga4",
                        metric_key=db_key,
                        dimension_key=row["dimension_key"],
                        dimension_value=row["dimension_value"],
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
        return len(metrics_to_insert)

    except Exception as e:
        error_msg = str(e)
        if isinstance(e, InvalidArgument | PermissionDenied):
            error_msg = getattr(e, "message", str(e))

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

def get_ai_referrals(
    db: Session, client_id: uuid.UUID, start_date: date, end_date: date
) -> list[dict]:
    """Fetch AI-referral sessions from GA4 using the sessionSource dimension."""
    conn = db.query(Connection).filter_by(
        client_id=client_id, provider=ProviderType.ga4, status=ConnectionStatus.connected
    ).first()

    if not conn or not conn.property_id:
        return []

    creds = get_google_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    property_id = conn.property_id
    if not property_id.startswith("properties/"):
        property_id = f"properties/{property_id}"

    # We want sessionSource dimension and sessions metric
    request = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name="sessionSource")],
        metrics=[GA4Metric(name="sessions")],
        date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"))],
    )

    try:
        response = client.run_report(request=request)
    except Exception as e:
        logger.error(f"GA4 AI referrals pull failed for client {client_id}: {e}")
        return []

    ai_sources = ["chatgpt", "perplexity", "claude", "gemini", "copilot", "poe", "phind", "android-app", "com.openai.chatgpt"]
    
    results = {}
    
    for row in response.rows:
        source = row.dimension_values[0].value.lower()
        sessions = int(row.metric_values[0].value)
        
        # Check if source matches any of our known AI sources
        if any(ai_src in source for ai_src in ai_sources):
            # Normalize names
            display_name = "ChatGPT" if "chatgpt" in source or "openai" in source else source.capitalize()
            display_name = "Perplexity" if "perplexity" in source else display_name
            display_name = "Claude" if "claude" in source or "anthropic" in source else display_name
            display_name = "Gemini" if "gemini" in source else display_name
            display_name = "Copilot" if "copilot" in source else display_name
            display_name = "Poe" if "poe" in source else display_name
            display_name = "Phind" if "phind" in source else display_name
            
            results[display_name] = results.get(display_name, 0) + sessions

    # Sort descending
    sorted_results = [{"source": k, "sessions": v} for k, v in sorted(results.items(), key=lambda item: item[1], reverse=True)]
    
    return sorted_results
