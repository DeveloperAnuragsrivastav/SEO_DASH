from __future__ import annotations
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType
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


def _pull_gsc_data_with_retry(property_id: str, start_date: date, end_date: date,
                              with_previous: bool = True) -> dict:
    """Every Search Console query a report needs for one window, run side by
    side. `with_previous` also fetches the pages of the window just before,
    for "trending up", which a pull of the comparison period does not need."""
    from concurrent.futures import ThreadPoolExecutor

    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - (end_date - start_date)

    def q(dims, lo=start_date, hi=end_date, limit=25000, optional=False):
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
        def run():
            # One service per thread: the client library's HTTP object is not thread-safe.
            service = build("webmasters", "v3", credentials=get_google_credentials(), cache_discovery=False)
            return _execute_gsc_query(service, property_id, lo, hi, dims, row_limit=limit)

        def guarded():
            if not optional:
                return run()
            try:
                return run()
            except Exception as e:  # the rest of the pull is still good without it
                logger.warning("GSC %s unavailable for %s: %s", dims, property_id, e)
                return []
        return guarded

    jobs = {
        # No dimensions: the true totals, as the GSC dashboard shows them.
        "totals": q(None),
        "date": q(["date"]),
        "page": q(["page"]),
        "query": q(["query"], limit=250, optional=True),
        "date_page": q(["date", "page"]),
    }
    if with_previous:
        jobs["prev_pages"] = q(["date", "page"], prev_start, prev_end, optional=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {k: pool.submit(fn) for k, fn in jobs.items()}
        got = {k: f.result() for k, f in futures.items()}

    row = (got["totals"] or [{}])[0]
    totals = {k: row.get(k, 0) for k in ("clicks", "impressions", "ctr", "position")}

    date_rows = got["date"]
    for r in date_rows:
        r["dimension_key"] = None
        r["dimension_value"] = None

    top_pages_clean = [
        {"page": r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
         "ctr": round(r.get("ctr", 0) * 100, 2), "position": round(r.get("position", 0), 1)}
        for r in sorted(got["page"], key=lambda r: r.get("clicks", 0), reverse=True)[:10]
    ]
    top_queries = [
        {"query": r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
         "ctr": round(r.get("ctr", 0) * 100, 2), "position": round(r.get("position", 0), 1)}
        for r in sorted(got["query"], key=lambda r: (r.get("clicks", 0), r.get("impressions", 0)), reverse=True)[:10]
    ]

    def paged(rows):
        for r in rows:
            r["dimension_key"] = "page"
            r["dimension_value"] = r["keys"][1]
        return rows

    return {
        "totals": totals,
        "top_pages": top_pages_clean,
        "top_queries": top_queries,
        "date_rows": date_rows,
        "dimension_rows": paged(got["date_page"]),
        "previous_page_rows": paged(got.get("prev_pages") or []),
        "previous_window": (prev_start, prev_end),
    }


def _metric_rows(provider: str, rows: list[dict], day_of, dims=None) -> list[tuple]:
    """Pulled rows as (provider, day, metric_key, dimension_key, dimension_value, value, source)."""
    out = []
    for row in rows:
        day = day_of(row)
        for key in ("clicks", "impressions", "ctr", "position"):
            out.append((provider, day, key, row.get("dimension_key"), row.get("dimension_value"),
                        float(row.get(key, 0) or 0), "api"))
    return out


def gsc_rows(result: dict, end_date: date) -> list[tuple]:
    """A pull as rows a report is built from."""
    day = lambda row: datetime.strptime(row["keys"][0], "%Y-%m-%d").date()
    rows = _metric_rows("gsc", result["date_rows"] + result["dimension_rows"] + (result.get("previous_page_rows") or []), day)
    # Queries are kept as one row per query for the whole period, on its last day.
    for q in result.get("top_queries") or []:
        for key in ("clicks", "impressions", "ctr", "position"):
            rows.append(("gsc", end_date, key, "query:period", q["query"], float(q.get(key, 0) or 0), "api"))
    return rows


def pull_gsc_data(db: Session, connection_id: uuid.UUID, start_date: date, end_date: date) -> dict:
    """Pull Search Console figures for a window. Nothing is stored: the rows
    come back with the totals, for the report being built to keep.

    Only the connection's own health (connected, last error) is recorded.
    """
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")
    if conn.provider != ProviderType.gsc:
        raise ValueError(f"Cannot pull GSC data for provider: {conn.provider}")

    try:
        result = _pull_gsc_data_with_retry(conn.property_id, start_date, end_date)
    except Exception as e:
        error_msg = str(e)
        if isinstance(e, HttpError):
            import json
            try:
                error_msg = json.loads(e.content).get("error", {}).get("message", error_msg)
            except Exception:
                pass
        logger.error(f"GSC pull failed for connection {connection_id}: {error_msg}")
        db.rollback()
        conn.status = ConnectionStatus.error
        conn.last_error = error_msg
        db.commit()
        raise ValueError(f"GSC pull failed: {error_msg}") from e

    rows = gsc_rows(result, end_date)

    conn.last_verified_at = datetime.now(timezone.utc)
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.status = ConnectionStatus.connected
    conn.last_error = None
    db.commit()

    return {
        "totals": result["totals"],
        "top_pages": result["top_pages"],
        "top_queries": result.get("top_queries", []),
        "rows": rows,
    }
