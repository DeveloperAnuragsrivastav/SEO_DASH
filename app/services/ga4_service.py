from __future__ import annotations
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, RunReportRequest
from google.analytics.data_v1beta.types import Metric as GA4Metric
from google.api_core.exceptions import InvalidArgument
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType
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

    dimensions = list(dimensions)  # retried calls must see the same list
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _execute_ga4_events(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Every event the property recorded, by name and day.

    The report's Leads & Conversion figures are individual events — a thank-you
    page view, a tap on a phone number, a mailto click — and GA4 only names
    those through the eventName dimension. The single `conversions` total the
    other query returns cannot be broken back apart into them.
    """
    if not property_id.startswith("properties/"):
        property_id = f"properties/{property_id}"

    request = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name="date"), Dimension(name="eventName")],
        metrics=[
            GA4Metric(name="eventCount"),
            GA4Metric(name="eventValue"),
        ],
        date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"),
                               end_date=end_date.strftime("%Y-%m-%d"))],
    )

    response = client.run_report(request=request)
    rows: list[dict] = []
    for row in response.rows:
        rows.append({
            "date": row.dimension_values[0].value,
            "event": row.dimension_values[1].value,
            "count": float(row.metric_values[0].value),
            "value": float(row.metric_values[1].value),
        })
    return rows


# The GA4 comparison tables the report prints: which dimension each is broken
# down by, the Metric dimension_key its rows are stored under, and the GA4
# metrics fetched for it, with the field name each is kept as. Only counts and
# durations are kept; rates and averages are worked out from them when shown.
#
# Channels are fetched per day, since every one of their figures adds up
# across days. Countries carry active and new users, which do not — the same
# person visits on several days — so they are fetched as one total for the
# whole period, stored on its last day, to match what GA4 itself shows.
BREAKDOWNS: dict[str, dict] = {
    "channels": {
        "dimension": "sessionDefaultChannelGroup",
        "stored_as": "sessionDefaultChannelGroup",
        "name": "channel",
        "daily": True,
        "metrics": (
            ("sessions", "sessions"),
            ("engagedSessions", "engaged_sessions"),
            ("userEngagementDuration", "engagement_seconds"),
            ("eventCount", "event_count"),
            ("keyEvents", "key_events"),
        ),
    },
    "countries_detail": {
        "dimension": "country",
        "stored_as": "country:period",
        "name": "country",
        "daily": False,
        "metrics": (
            ("activeUsers", "active_users"),
            ("newUsers", "new_users"),
            ("sessions", "sessions"),
            ("engagedSessions", "engaged_sessions"),
            ("userEngagementDuration", "engagement_seconds"),
            ("eventCount", "event_count"),
            ("keyEvents", "key_events"),
            ("totalRevenue", "revenue"),
        ),
    },
}


def breakdown_fields(key: str) -> tuple[str, ...]:
    return tuple(field for _, field in BREAKDOWNS[key]["metrics"])


def _execute_ga4_breakdown(
    client: BetaAnalyticsDataClient,
    property_id: str,
    start_date: date,
    end_date: date,
    key: str,
) -> list[dict]:
    """One of the BREAKDOWNS for a window: rows of {name, [date], fields}.

    `keyEvents` is GA4's current name for conversions; a property or API
    version that does not know it yet is asked for `conversions` instead.
    """
    spec = BREAKDOWNS[key]
    if not property_id.startswith("properties/"):
        property_id = f"properties/{property_id}"
    dims = ([Dimension(name="date")] if spec["daily"] else []) + [Dimension(name=spec["dimension"])]
    fields = breakdown_fields(key)

    last_error: Exception | None = None
    for key_metric in ("keyEvents", "conversions"):
        names = [key_metric if m == "keyEvents" else m for m, _ in spec["metrics"]]
        request = RunReportRequest(
            property=property_id,
            dimensions=dims,
            metrics=[GA4Metric(name=n) for n in names],
            date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"),
                                   end_date=end_date.strftime("%Y-%m-%d"))],
            limit=100000,
        )
        try:
            response = client.run_report(request=request)
        except InvalidArgument as e:
            last_error = e
            continue
        rows: list[dict] = []
        for row in response.rows:
            dv = [d.value for d in row.dimension_values]
            rows.append({
                **({"date": dv[0]} if spec["daily"] else {}),
                "name": dv[-1],
                **dict(zip(fields, (float(v.value or 0) for v in row.metric_values))),
            })
        return rows
    raise last_error  # type: ignore[misc]


def breakdown_totals(key: str, rows) -> list[dict]:
    """Rows of one breakdown (any mix of its fields, each named by `name` or
    by the breakdown's own name key) added up into one row per name, biggest
    first."""
    spec = BREAKDOWNS[key]
    fields = breakdown_fields(key)
    merged: dict[str, dict] = {}
    for r in rows:
        name = str(r.get("name") or r.get(spec["name"]) or "").strip()
        if not name:
            continue
        entry = merged.setdefault(name, {spec["name"]: name, **{f: 0.0 for f in fields}})
        for f in fields:
            entry[f] += float(r.get(f) or 0)
    out = [{**e, **{f: round(e[f], 2) for f in fields}} for e in merged.values()]
    return sorted(out, key=lambda e: (e.get("sessions", 0), e.get("active_users", 0)), reverse=True)


def _pull_ga4_data_structured(property_id: str, start_date: date, end_date: date,
                              with_previous: bool = True) -> dict:
    """Every GA4 query a report needs for one window, run side by side — each
    is about a second, and one after another they added up to a minute.

    `with_previous` also fetches the comparison tables for the window just
    before, which a pull of the comparison period itself does not need.
    """
    from concurrent.futures import ThreadPoolExecutor

    creds = get_google_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - (end_date - start_date)

    def query(dims: list[str]):
        return lambda: _execute_ga4_query(client, property_id, start_date, end_date, list(dims))

    def safe(fn, name: str):
        def run():
            try:
                return fn()
            except Exception as e:  # the rest of the pull is still good without it
                logger.warning("GA4 %s unavailable for %s: %s", name, property_id, e)
                return []
        return run

    jobs = {
        "totals": query([]),
        "date": query(["date"]),
        "sources": query(["sessionSource"]),
        "devices": query(["deviceCategory"]),
        "pages": query(["pagePath"]),
        "channels": query(["sessionDefaultChannelGroup"]),
        "countries": query(["country"]),
        "d_sources": query(["date", "sessionSource"]),
        "d_devices": query(["date", "deviceCategory"]),
        "d_pages": query(["date", "pagePath"]),
        # Countries are kept too, so a report can show them.
        "d_countries": query(["date", "country"]),
        # Named events: the only place the individual lead actions live.
        "events": safe(lambda: _execute_ga4_events(client, property_id, start_date, end_date), "events"),
    }
    for key in BREAKDOWNS:
        jobs[f"bd:{key}"] = safe(lambda k=key: _execute_ga4_breakdown(client, property_id, start_date, end_date, k), key)
        if with_previous:
            jobs[f"bdp:{key}"] = safe(lambda k=key: _execute_ga4_breakdown(client, property_id, prev_start, prev_end, k), key)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {name: pool.submit(fn) for name, fn in jobs.items()}
        got = {name: f.result() for name, f in futures.items()}

    totals_rows = got["totals"]
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

    date_rows = got["date"]
    top_sources = sorted(got["sources"], key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    sources_clean = [{"source": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in top_sources]
    devices_clean = [{"device": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in got["devices"]]
    top_pages = sorted(got["pages"], key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    pages_clean = [{"page": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"], "conversions": r["conversions"]} for r in top_pages]
    totals["organic_sessions"] = next(
        (r.get("sessions", 0) for r in got["channels"] if r.get("dimension_value", "").lower() == "organic search"), 0)
    top_countries = sorted(got["countries"], key=lambda x: x.get("sessions", 0), reverse=True)[:10]
    countries_clean = [{"country": r["dimension_value"], "sessions": r["sessions"], "users": r["activeUsers"]} for r in top_countries]
    all_dim_rows = got["d_sources"] + got["d_devices"] + got["d_pages"] + got["d_countries"]

    event_rows = got["events"]
    # The block a report reads carries the event totals, not the daily rows,
    # so a live pull and a pull read back from storage look the same.
    event_totals: dict[str, float] = {}
    for row in event_rows:
        name = (row.get("event") or "").strip()
        if name:
            event_totals[name] = event_totals.get(name, 0.0) + float(row.get("count") or 0)
    totals["events"] = {k: round(v) for k, v in sorted(event_totals.items(), key=lambda kv: -kv[1])}

    breakdowns: dict[str, dict] = {
        key: {"rows": got[f"bd:{key}"], "rows_previous": got.get(f"bdp:{key}", [])} for key in BREAKDOWNS
    }

    return {
        "totals": totals,
        **{k: breakdown_totals(k, b["rows"]) for k, b in breakdowns.items()},
        **{f"{k}_previous": breakdown_totals(k, b["rows_previous"]) for k, b in breakdowns.items()},
        "breakdowns": breakdowns,
        "previous_window": (prev_start, prev_end),
        "event_rows": event_rows,
        "date_rows": date_rows,
        "dimension_rows": all_dim_rows,
        "traffic_sources": sources_clean,
        "devices": devices_clean,
        "top_pages": pages_clean,
        "countries": countries_clean,
    }


def ga4_rows(result: dict, start_date: date, end_date: date) -> list[tuple]:
    """A pull as rows a report is built from:
    (provider, day, metric_key, dimension_key, dimension_value, value, source)."""
    metric_key_map = {
        "sessions": "sessions",
        "activeUsers": "users",
        "engagedSessions": "engaged_sessions",
        "conversions": "conversions",
        "purchaseRevenue": "revenue",
        "averageSessionDuration": "avg_session_duration",
        "addToCarts": "add_to_carts",
    }

    def day_of(row: dict, fallback: date) -> date:
        date_str = row.get("date")
        return datetime.strptime(date_str, "%Y%m%d").date() if date_str and len(date_str) == 8 else fallback

    rows: list[tuple] = []
    for row in result["date_rows"] + result["dimension_rows"]:
        day = day_of(row, start_date)
        for ga4_key, key in metric_key_map.items():
            rows.append(("ga4", day, key, row.get("dimension_key"), row.get("dimension_value"),
                         float(row.get(ga4_key, 0) or 0), "api"))
    for row in result.get("event_rows") or []:
        name = (row.get("event") or "").strip()
        if name:
            rows.append(("ga4", day_of(row, start_date), "event_count", "eventName", name,
                         float(row.get("count") or 0), "api"))
    prev_start, prev_end = result["previous_window"]
    for key, b in (result.get("breakdowns") or {}).items():
        spec = BREAKDOWNS[key]
        for window_rows, last_day in ((b["rows"], end_date), (b["rows_previous"], prev_end)):
            for row in window_rows:
                day = day_of(row, last_day)
                for field in breakdown_fields(key):
                    rows.append(("ga4", day, field, spec["stored_as"], row.get("name"),
                                 float(row.get(field) or 0), "api"))

    return rows


def pull_ga4_data(
    db: Session,
    connection_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    trigger_time: datetime | None = None,
) -> dict:
    """Pull Analytics figures for a window. Nothing is stored: the daily rows
    come back with the totals, for the report being built to keep.

    Only the connection's own health (connected, last error) is recorded.
    """
    conn = db.get(Connection, connection_id)
    if not conn:
        raise ValueError("Connection not found")
    if conn.provider != ProviderType.ga4:
        raise ValueError(f"Cannot pull GA4 data for provider: {conn.provider}")

    if start_date is None or end_date is None:
        if trigger_time is None:
            trigger_time = datetime.now(timezone.utc)
        start_date, end_date = calculate_previous_month(conn.property_tz, trigger_time)
    assert start_date is not None and end_date is not None

    try:
        result = _pull_ga4_data_structured(conn.property_id, start_date, end_date)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"GA4 pull failed for connection {connection_id}: {error_msg}")
        db.rollback()
        conn.status = ConnectionStatus.error
        conn.last_error = error_msg
        db.commit()
        raise ValueError(f"GA4 pull failed: {error_msg}") from e

    rows = ga4_rows(result, start_date, end_date)

    conn.last_verified_at = datetime.now(timezone.utc)
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.status = ConnectionStatus.connected
    conn.last_error = None
    db.commit()

    return {
        "totals": result["totals"],
        "traffic_sources": result["traffic_sources"],
        "devices": result["devices"],
        "top_pages": result["top_pages"],
        "countries": result["countries"],
        **{k: result.get(k, []) for k in BREAKDOWNS},
        "rows": rows,
    }
