from __future__ import annotations
import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

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
    service, property_id: str, start_date: date, end_date: date,
    dimensions: list[str] | None = None, row_limit: int = 25000,
) -> list[dict]:
    """Execute a single Search Console query and return the rows."""
    body: dict[str, Any] = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "rowLimit": row_limit,
        "dataState": "all",
    }
    if dimensions:
        body["dimensions"] = dimensions
    response = service.searchanalytics().query(siteUrl=property_id, body=body).execute()
    return response.get("rows", [])  # type: ignore


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _pull_gsc_data_with_retry(property_id: str, start_date: date, end_date: date) -> dict:
    """Pull GSC data with retries. Returns a structured dict with totals + breakdowns."""
    creds = get_google_credentials()
    service = build("webmasters", "v3", credentials=creds, cache_discovery=False)

    # ── 1. TRUE TOTALS: dimension-less query ─────────────────────────
    # This gives us the exact same numbers as the GSC dashboard.
    # No dimensions = no anonymization filtering = accurate totals.
    totals_rows = _execute_gsc_query(service, property_id, start_date, end_date, dimensions=None)
    if totals_rows:
        row = totals_rows[0]  # Single row with aggregate data
        totals = {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        }
    else:
        totals = {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

    # ── 2. Per-date rows (for daily trends + DB storage) ─────────────
    date_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["date"])
    for row in date_rows:
        row["dimension_key"] = None
        row["dimension_value"] = None

    # ── 3. Page-level breakdown ──────────────────────────────────────
    page_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["page"])
    top_pages = sorted(page_rows, key=lambda r: r.get("clicks", 0), reverse=True)[:10]
    top_pages_clean = [
        {
            "page": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        }
        for r in top_pages
    ]

    # ── 4. Removed Query-level and Device-level breakdown as requested ──

    # Prepare dimension-level rows for DB storage (page by date)
    all_dimension_rows = []
    page_date_rows = _execute_gsc_query(service, property_id, start_date, end_date, ["date", "page"])
    for row in page_date_rows:
        row["dimension_key"] = "page"
        row["dimension_value"] = row["keys"][1]
        all_dimension_rows.append(row)

    return {
        "totals": totals,
        "top_pages": top_pages_clean,
        "date_rows": date_rows,
        "dimension_rows": all_dimension_rows,
    }

def pull_gsc_data(db: Session, connection_id: uuid.UUID, start_date: date, end_date: date) -> dict:
    """Pull GSC data for a connection, managing SyncRun and retries.
    
    Returns a structured dict with totals, top_pages, top_queries, devices
    for direct use in snapshot generation.
    """
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")

    if conn.provider != ProviderType.gsc:
        raise ValueError(f"Cannot pull GSC data for provider: {conn.provider}")

    started_at = datetime.now(timezone.utc)

    try:
        result = _pull_gsc_data_with_retry(conn.property_id, start_date, end_date)

        # Store per-date rows + dimension rows in DB for historical tracking / SearchConsole admin page
        metrics_to_insert = []
        all_raw_rows = result["date_rows"] + result["dimension_rows"]

        for row in all_raw_rows:
            captured_on = datetime.strptime(row["keys"][0], "%Y-%m-%d").date()

            for metric_key in ["clicks", "impressions", "ctr", "position"]:
                val = row.get(metric_key, 0)
                metrics_to_insert.append(
                    Metric(
                        client_id=conn.client_id,
                        provider="gsc",
                        metric_key=metric_key,
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

        # Return the structured data for snapshot use
        return {
            "totals": result["totals"],
            "top_pages": result["top_pages"],
            "rows_stored": len(metrics_to_insert),
        }

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
