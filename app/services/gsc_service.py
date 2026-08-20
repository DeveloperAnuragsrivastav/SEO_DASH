from __future__ import annotations
import logging
import uuid
from datetime import date, datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, MetricSource, ProviderType, SyncStatus
from app.models.metric import Metric
from app.models.sync_run import SyncRun
from app.services.google_clients import get_google_credentials

logger = logging.getLogger(__name__)


def _execute_gsc_query(
    service, property_id: str, start_date: date, end_date: date, dimensions: list[str]
) -> list[dict]:
    """Execute a single Search Console query and return the rows."""
    request = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": dimensions,
    }
    response = service.searchanalytics().query(siteUrl=property_id, body=request).execute()
    return response.get("rows", [])  # type: ignore


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _pull_gsc_data_with_retry(property_id: str, start_date: date, end_date: date) -> list[dict]:
    """Pull GSC data. Retries on ANY exception (network, API, etc) up to 3 times."""
    creds = get_google_credentials()
    service = build("webmasters", "v3", credentials=creds, cache_discovery=False)

    all_rows = []

    # 1. Overall site metrics (just date)
    date_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["date"])
    for row in date_rows:
        row["dimension_key"] = None
        row["dimension_value"] = None
        all_rows.append(row)

    # 2. Page-level metrics
    page_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["date", "page"])
    for row in page_rows:
        row["dimension_key"] = "page"
        row["dimension_value"] = row["keys"][1]
        all_rows.append(row)

    # 3. Query-level metrics
    query_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["date", "query"])
    for row in query_rows:
        row["dimension_key"] = "query"
        row["dimension_value"] = row["keys"][1]
        all_rows.append(row)

    return all_rows


def pull_gsc_data(db: Session, connection_id: uuid.UUID, start_date: date, end_date: date) -> int:
    """Pull GSC data for a connection, managing SyncRun and retries."""
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")

    if conn.provider != ProviderType.gsc:
        raise ValueError(f"Cannot pull GSC data for provider: {conn.provider}")

    started_at = datetime.now(timezone.utc)

    try:
        raw_rows = _pull_gsc_data_with_retry(conn.property_id, start_date, end_date)

        metrics_to_insert = []
        for row in raw_rows:
            captured_on = datetime.strptime(row["keys"][0], "%Y-%m-%d").date()

            for metric_key in ["clicks", "impressions", "ctr", "position"]:
                val = row.get(metric_key, 0)
                metrics_to_insert.append(
                    Metric(
                        client_id=conn.client_id,
                        provider="gsc",
                        metric_key=metric_key,
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
                Metric.provider == "gsc",
                Metric.source == MetricSource.api,
                Metric.captured_on >= start_date,
                Metric.captured_on <= end_date,
            ).delete(synchronize_session=False)

            db.add_all(metrics_to_insert)

        sync_run = SyncRun(
            client_id=conn.client_id,
            provider="gsc",
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
        if isinstance(e, HttpError):
            import json
            try:
                err_dict = json.loads(e.content)
                error_msg = err_dict.get("error", {}).get("message", error_msg)
            except Exception:
                pass

        logger.error(f"GSC pull failed for connection {connection_id}: {error_msg}")

        db.rollback()

        sync_run = SyncRun(
            client_id=conn.client_id,
            provider="gsc",
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

        raise ValueError(f"GSC pull failed: {error_msg}") from e
