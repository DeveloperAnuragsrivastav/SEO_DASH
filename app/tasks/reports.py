"""Building a report draft, in the background of the request that asked for it.

Only the draft is written: Google is pulled into memory for the current
cycle and the one it is compared with, and the figures are kept inside the
report. The month-on-month sheets are untouched until the report is published.
"""
from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import select, text

from app.database import SessionLocal, engine
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, ReportStatus
from app.models.report_snapshot import ReportSnapshot
from app.services.report_period import build_report_data, cycle_bounds, previous_window, pulled

logger = logging.getLogger(__name__)


def pull_for_report(db, client_id: uuid.UUID, end_date: datetime.date, months: int,
                    providers: tuple[str, ...] = ("gsc", "ga4", "gbp"),
                    start: datetime.date | None = None) -> tuple[list[tuple], dict]:
    """Pull every connected Google source for the report's current cycle and
    the period it is compared with — all of them at once, since each is a
    handful of slow network calls. Returns the rows and the current cycle's
    true totals per provider. A source that fails is left out, not fatal."""
    from concurrent.futures import ThreadPoolExecutor
    from app.services import ga4_service, gbp_service, gsc_service

    # Only the current month, and the month before it for its comparison and
    # its trending pages. Every earlier month is read from what was saved when
    # it was published — nothing old is pulled again.
    # A first report may cover a period the person picked; every later one
    # is one cycle. Either way it is compared with as long a stretch before.
    start_date = start or cycle_bounds(end_date, 0)[0]
    compare_start, compare_end = previous_window(end_date, 1, start)
    connections = [
        c for c in db.execute(select(Connection).where(Connection.client_id == client_id)).scalars().all()
        if c.status == ConnectionStatus.connected and c.provider.value in providers
    ]

    # Network only in the threads; the session stays on this one.
    fetchers = {
        ProviderType.gsc: lambda pid, lo, hi, cur: gsc_service._pull_gsc_data_with_retry(pid, lo, hi, with_previous=cur),
        ProviderType.ga4: lambda pid, lo, hi, cur: ga4_service._pull_ga4_data_structured(pid, lo, hi, with_previous=cur),
        ProviderType.gbp: lambda pid, lo, hi, cur: gbp_service._fetch_gbp_metrics(pid, lo, hi),
    }
    jobs = []
    for conn in connections:
        for lo, hi, cur in ((start_date, end_date, True), (compare_start, compare_end, False)):
            jobs.append((conn, lo, hi, cur))
    results: dict = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {(j[0].id, j[3]): pool.submit(fetchers[j[0].provider], j[0].property_id, j[1], j[2], j[3]) for j in jobs}
            for key, f in futures.items():
                try:
                    results[key] = f.result()
                except Exception as e:
                    results[key] = e

    rows: list[tuple] = []
    live: dict[str, Any] = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    for conn in connections:
        current, before = results.get((conn.id, True)), results.get((conn.id, False))
        if isinstance(current, Exception):
            logger.warning("Pull failed for %s (%s): %s", conn.provider.value, client_id, current)
            conn.status = ConnectionStatus.error
            conn.last_error = str(current)[:1000]
            continue
        if isinstance(before, Exception):
            logger.warning("Comparison pull failed for %s (%s): %s", conn.provider.value, client_id, before)
            before = None
        if conn.provider == ProviderType.gsc:
            rows += gsc_service.gsc_rows(current, end_date)
            if before:
                rows += gsc_service.gsc_rows(before, compare_end)
            live["gsc"] = {**current["totals"], "top_pages": current["top_pages"], "top_queries": current.get("top_queries", [])}
        elif conn.provider == ProviderType.ga4:
            rows += ga4_service.ga4_rows(current, start_date, end_date)
            if before:
                rows += ga4_service.ga4_rows(before, compare_start, compare_end)
            live["ga4"] = {
                **current["totals"],
                "traffic_sources": current["traffic_sources"],
                "devices": current["devices"],
                "top_pages": current["top_pages"],
                "countries": current.get("countries", []),
                "channels": current.get("channels", []),
                "countries_detail": current.get("countries_detail", []),
            }
        else:
            for raw in (current, before or []):
                rows += [("gbp", r["date"], r["metric_key"], None, None, float(r["value"]), "api") for r in raw]
        conn.status = ConnectionStatus.connected
        conn.last_error = None
        conn.last_verified_at = now
        conn.last_sync_at = now
    db.commit()
    return rows, live


def generate_snapshot_report(client_id_str: str, months: int = 1, end_date: datetime.date | None = None,
                             start_date: datetime.date | None = None):
    """Build (or rebuild) the draft for the last finished month — on any day
    of October, September 1–30. Reports run month on month: September's is
    made in October, October's in November."""
    from app.services.report_period import last_complete_month

    client_id = uuid.UUID(client_id_str)
    end_date = end_date or last_complete_month()
    lock_id = hash(f"{client_id}-{end_date.isoformat()}") & 0x7FFFFFFFFFFFFFFF

    with engine.connect() as lock_conn:
        if not lock_conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar():
            logger.warning("Report generation already in progress for %s %s", client_id, end_date)
            return "Already in progress"

        db = SessionLocal()
        try:
            client = db.get(Client, client_id)
            if not client:
                return "Client not found"

            existing = db.execute(
                select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.end_date == end_date)
            ).scalars().first()
            if existing and existing.status == ReportStatus.published:
                return "Report is published"

            first_start = start_date if months == 1 else None
            rows, live = pull_for_report(db, client_id, end_date, months, start=first_start)
            with pulled(rows):
                snapshot: dict[str, Any] = build_report_data(db, client_id, end_date, months, live=live,
                                                             start=first_start)
            if first_start:
                snapshot["own_start"] = first_start.isoformat()   # kept for every rebuild of this report
            window_start = datetime.date.fromisoformat(snapshot["period"]["start"])

            # No AI here: the summaries, subtitles and plan are written only
            # when someone presses "Write with AI" in the builder. Anything
            # already on this draft is carried over below.

            if existing:
                for keep in ("included_sections", "included_items", "copy", "narration", "narration_source",
                             "subtitle_ai", "subtitles_drafted", "links", "activities", "hidden_slides", "hidden_cards",
                             "next_month_plan", "plan_source", "own_start"):
                    if keep in (existing.snapshot or {}):
                        snapshot[keep] = existing.snapshot[keep]
                existing.start_date = window_start
                existing.snapshot = snapshot
                existing.generated_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                return str(existing.id)

            # A new month inherits the wording the agency settled on, so a
            # renamed card or heading is chosen once per client.
            previous = db.execute(
                select(ReportSnapshot)
                .where(ReportSnapshot.client_id == client_id, ReportSnapshot.end_date < end_date)
                .order_by(ReportSnapshot.end_date.desc()).limit(1)
            ).scalar_one_or_none()
            inherited = (previous.snapshot or {}).get("copy") if previous else None
            if isinstance(inherited, dict) and inherited:
                # Headings carry over; subtitles the AI wrote quote last month's figures.
                ai_written = set((previous.snapshot or {}).get("subtitle_ai") or [])
                inherited = {**inherited, "subtitles": {k: v for k, v in (inherited.get("subtitles") or {}).items()
                                                        if k not in ai_written}}
                snapshot["copy"] = inherited

            report = ReportSnapshot(
                client_id=client_id,
                start_date=window_start,
                end_date=end_date,
                status=ReportStatus.draft,
                snapshot=snapshot,
                generated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(report)
            db.commit()
            return str(report.id)
        except Exception:
            logger.exception("Report generation failed for %s.", client_id)
            db.rollback()
            raise
        finally:
            db.close()
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
