"""Report periods: 30-day cycles, and reports that combine several of them.

A report covers one or more consecutive 30-day cycles ending on its anchor
date. Nothing a draft uses is stored on its own: the current cycle (and the
one it is compared with) is pulled from Google into memory while the report
is built, and what the builder types is kept inside the report. Older months
come from the month-on-month sheets, which only publishing writes to.
Figures are combined with the arithmetic each one needs — clicks add up, a
click-through rate does not.
"""
from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_prompt import AiPrompt
from app.models.enums import ReportStatus
from app.models.keyword import Keyword
from app.models.report_snapshot import ReportSnapshot
from app.services import sheets
from app.services.ga4_service import BREAKDOWNS, breakdown_fields, breakdown_totals

CYCLE_DAYS = 30
MAX_CYCLES = 12
_ONE = datetime.timedelta(days=1)

# The per-cycle figures kept for the month-by-month views.
PERIOD_KEYS: dict[str, tuple[str, ...]] = {
    "gsc": ("clicks", "impressions", "ctr", "position"),
    "ga4": ("sessions", "users", "engaged_sessions", "conversions"),
    "gbp": ("calls", "direction_requests", "website_clicks", "bookings"),
}

# Which snapshot keys each report section owns.
SECTION_KEYS: dict[str, tuple[str, ...]] = {
    "gsc": ("gsc",),
    "ga4": ("ga4",),
    "gbp": ("gbp",),
    "rankings": ("rankings",),
    "ai_visibility": ("ai_visibility", "ai_compare"),
    "links": ("links",),
    "work": ("activities", "screenshots"),
}

_GA4_ADDITIVE = ("sessions", "engaged_sessions", "conversions", "revenue", "add_to_carts", "organic_sessions")
_GA4_LISTS = (
    ("traffic_sources", "sessionSource", "source"),
    ("devices", "deviceCategory", "device"),
    ("top_pages", "pagePath", "page"),
    ("countries", "country", "country"),
)


# Rows pulled for the report being built: (provider, day, metric_key,
# dimension_key, dimension_value, value, source). Set around a build with
# `pulled(rows)`; nothing outside a build ever reads them.
_PULLED: ContextVar[tuple] = ContextVar("report_pulled_rows", default=())


@contextmanager
def pulled(rows: Iterable[tuple]):
    token = _PULLED.set(tuple(rows or ()))
    try:
        yield
    finally:
        _PULLED.reset(token)


# ── Cycles ──────────────────────────────────────────────────────────────────

def _shift_months(day: datetime.date, months: int) -> datetime.date:
    """The same day number `months` later (or earlier). Only used with days
    1–28, which every month has."""
    y, m = divmod(day.year * 12 + day.month - 1 + months, 12)
    return day.replace(year=y, month=m + 1)


def cycle_start_day(end: datetime.date) -> int:
    """The day of the month a client's reports start on: the day after a
    report ends. 1 is calendar months."""
    return (end + _ONE).day


def valid_period_end(end: datetime.date) -> bool:
    """A period may end on a month's last day or on the 1st–27th, so the next
    one starts on a date every month has (the 1st–28th)."""
    return cycle_start_day(end) <= 28


def last_complete_month(today: Optional[datetime.date] = None) -> datetime.date:
    """The last day of the most recent month that has ended. On any day of
    October that is 30 September."""
    return (today or datetime.date.today()).replace(day=1) - _ONE


def due_cycle_end(last_end: datetime.date, today: Optional[datetime.date] = None) -> datetime.date:
    """The end of the latest period, on the client's own cycle, that is over
    by today. Reports ending 4 Oct run 5th to 4th: on 7 Nov that is 4 Nov."""
    today = today or datetime.date.today()
    nxt = last_end + _ONE                       # the day the next period starts
    if not valid_period_end(last_end):
        return last_complete_month(today)
    k = 0
    while _shift_months(nxt, k + 1) - _ONE < today:
        k += 1
    return _shift_months(nxt, k) - _ONE


def next_cycle_opens(end: datetime.date) -> datetime.date:
    """The day the period after the one ending `end` is over and can be made."""
    if not valid_period_end(end):
        return (end.replace(day=1) + datetime.timedelta(days=32)).replace(day=1) + datetime.timedelta(days=31)
    return _shift_months(end + _ONE, 1)


def first_period_suggestion(today: Optional[datetime.date] = None) -> tuple[datetime.date, datetime.date]:
    """What a client's first report offers before anyone picks: the month up
    to yesterday (5 Sep – 4 Oct on 5 Oct). If yesterday is the 28th–30th the
    next period could not start on the same date every month, so it ends on
    the 27th instead."""
    today = today or datetime.date.today()
    end = today - _ONE
    if not valid_period_end(end):
        end = end.replace(day=27)
    return _shift_months(end + _ONE, -1), end


def cycle_bounds(anchor_end: datetime.date, index: int) -> tuple[datetime.date, datetime.date]:
    """Period `index` counted back from the one ending on `anchor_end` (0).

    Every period runs from the same date in one month to the day before it
    in the next — the date fixed by the client's first report. Reports from
    the 1st are calendar months (1–30 September); a client who started on
    the 5th runs 5 Sep – 4 Oct, 5 Oct – 4 Nov… No two periods overlap and none
    is skipped.
    """
    nxt = anchor_end + _ONE
    if valid_period_end(anchor_end):
        return _shift_months(nxt, -(index + 1)), _shift_months(nxt, -index) - _ONE
    # An end that breaks the rule (older data): the calendar month instead.
    import calendar
    y, m = divmod(anchor_end.year * 12 + anchor_end.month - 1 - index, 12)
    first = datetime.date(y, m + 1, 1)
    return first, first.replace(day=calendar.monthrange(y, m + 1)[1])


def report_cycles(anchor_end: datetime.date, months: int) -> list[tuple[datetime.date, datetime.date]]:
    """The cycles a report of `months` covers, oldest first."""
    return [cycle_bounds(anchor_end, i) for i in reversed(range(months))]


def short_range(start: datetime.date, end: datetime.date) -> str:
    if start.year == end.year:
        return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
    return f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"


def period_name(start: datetime.date, end: datetime.date) -> str:
    """A whole calendar month by its name ("September 2026"); any other
    period by its dates ("5 Sep – 4 Oct 2026")."""
    import calendar
    if start.day == 1 and start.year == end.year and start.month == end.month \
            and end.day == calendar.monthrange(end.year, end.month)[1]:
        return end.strftime("%B %Y")
    return short_range(start, end)


def cycle_labels(cycles: list[tuple[datetime.date, datetime.date]]) -> list[str]:
    """Each period's name: a calendar month by name, any other by its dates."""
    return [period_name(s, e) for s, e in cycles]


def cycle_sources(published: set, end: datetime.date) -> dict[str, bool]:
    """Whether a cycle's month has been published, and so has final figures."""
    done = sheets.cycle_month(end) in published
    return {k: done for k in ("gsc", "ga4", "gbp", "rankings", "ai_visibility", "links", "work")}


def anchor_for(db: Session, client_id: uuid.UUID, today: Optional[datetime.date] = None) -> dict:
    """Which period the next report covers, and whether it can be made now.

    A client's first report covers a period the person picks (first). After
    that, reports run on the same date every month, from the day after the
    last one ended, once each period is over:
    new    — the latest finished period has no report yet
    draft  — it has a draft; reopen that rather than make another
    locked — it is published; the next opens the day the next period ends
    """
    today = today or datetime.date.today()
    reports = db.execute(select(ReportSnapshot).where(ReportSnapshot.client_id == client_id)
                         .order_by(ReportSnapshot.end_date.desc())).scalars().all()
    if not reports:
        start, end = first_period_suggestion(today)
        return {"mode": "first", "anchor_end": end, "suggested_start": start, "report_id": None,
                "months": None, "days_remaining": 0}
    last = reports[0]
    due = due_cycle_end(last.end_date, today)
    info = {"report_id": str(last.id), "months": ((last.snapshot or {}).get("period") or {}).get("months", 1)}
    if due <= last.end_date:
        opens = next_cycle_opens(last.end_date)
        if last.status == ReportStatus.published:
            return {"mode": "locked", "anchor_end": last.end_date, "days_remaining": max(0, (opens - today).days),
                    "opens_on": opens, **info}
        return {"mode": "draft", "anchor_end": last.end_date, "days_remaining": 0, **info}
    return {"mode": "new", "anchor_end": due, "report_id": None, "months": None, "days_remaining": 0}


def timeline(db: Session, client_id: uuid.UUID, anchor_end: datetime.date) -> list[dict]:
    """The cycles a report ending on `anchor_end` can cover, oldest first.

    The current cycle is always offered — it is pulled or entered as the
    report is built. Older cycles are offered back to the first month that
    was never published, since a combined report has to be continuous.
    """
    published = set(sheets.published_months(db, client_id))
    found = []
    months_used: set = set()
    for i in range(MAX_CYCLES):
        start, end = cycle_bounds(anchor_end, i)
        sources = cycle_sources(published, end)
        # Each published month backs one cycle only: two 30-day cycles can end
        # in the same month, and the second would count that month twice.
        if i > 0 and (not any(sources.values()) or sheets.cycle_month(end) in months_used):
            break
        months_used.add(sheets.cycle_month(end))
        found.append((start, end, sources))
    found.reverse()
    labels = cycle_labels([(s, e) for s, e, _ in found])
    return [
        {
            "label": label,
            "range": short_range(s, e),
            "start": s.isoformat(),
            "end": e.isoformat(),
            "sources": sources,
            "current": e == anchor_end,
        }
        for (s, e, sources), label in zip(found, labels)
    ]


# ── Figures from stored daily rows ──────────────────────────────────────────

def _rows(db: Session, client_id: uuid.UUID, provider: str, start: datetime.date, end: datetime.date,
          dimension: Optional[str] = None) -> dict[tuple, float]:
    """(day, metric_key, dimension_value) → value, from the rows pulled for
    this build. A total is a row with no dimension ("" and NULL alike)."""
    out: dict[tuple, float] = {}
    for prov, day, key, dim_key, dim_value, value, _source in _PULLED.get():
        if prov != provider or not (start <= day <= end):
            continue
        if dimension is None:
            if dim_key:
                continue
        elif dim_key != dimension:
            continue
        out[(day, key, dim_value or None)] = float(value or 0)
    return out


def data_provenance(db: Session, client_id: uuid.UUID,
                    start: datetime.date, end: datetime.date) -> dict[str, dict]:
    """Where each section's figures came from: pulled from Google for this
    build, or entered in the builder."""
    out: dict[str, dict] = {}
    for provider in ("gsc", "ga4", "gbp"):
        days = [day for prov, day, *_ in _PULLED.get() if prov == provider and start <= day <= end]
        out[provider] = {"source": "api", "newest": max(days).isoformat()} if days else {"source": None, "newest": None}
    for section in ("rankings", "ai_visibility", "links", "work"):
        out[section] = {"source": "manual", "newest": None}
    return out


def _by_day(rows: dict[tuple, float]) -> dict[tuple, dict[str, float]]:
    grouped: dict[tuple, dict[str, float]] = defaultdict(dict)
    for (day, key, dim_value), value in rows.items():
        grouped[(day, dim_value)][key] = value
    return grouped


def _weighted_position(parts: list[tuple[float, float]]) -> float:
    """Average position weighted by impressions — a day with 5,000 impressions
    says more about where the site ranks than a day with 5."""
    impressions = sum(i for _, i in parts)
    if impressions:
        return sum(p * i for p, i in parts) / impressions
    positions = [p for p, _ in parts if p]
    return sum(positions) / len(positions) if positions else 0.0


def _gsc_block(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict:
    days = _by_day(_rows(db, client_id, "gsc", start, end))
    if not days:
        return {}
    clicks = sum(d.get("clicks", 0) for d in days.values())
    impressions = sum(d.get("impressions", 0) for d in days.values())
    block: dict[str, Any] = {
        "clicks": round(clicks),
        "impressions": round(impressions),
        "ctr": clicks / impressions if impressions else 0,
        "position": round(_weighted_position([(d.get("position", 0), d.get("impressions", 0)) for d in days.values()]), 2),
    }

    pages: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "parts": []})
    for (_, page), d in _by_day(_rows(db, client_id, "gsc", start, end, "page")).items():
        if not page:
            continue
        entry = pages[page]
        entry["clicks"] += d.get("clicks", 0)
        entry["impressions"] += d.get("impressions", 0)
        entry["parts"].append((d.get("position", 0), d.get("impressions", 0)))
    block["top_pages"] = _top_pages(
        {k: (v["clicks"], v["impressions"], _weighted_position(v["parts"])) for k, v in pages.items()}
    )

    # Day by day, for the Search Console chart.
    block["daily"] = [
        {"date": key[0].isoformat(), "clicks": round(d.get("clicks", 0)), "impressions": round(d.get("impressions", 0))}
        for key, d in sorted(days.items(), key=lambda kv: kv[0][0])
    ]

    # Top queries, kept as one row per query for each period.
    queries: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "parts": []})
    for (_, key, query), value in _rows(db, client_id, "gsc", start, end, "query:period").items():
        if not query:
            continue
        q = queries[query]
        if key in ("clicks", "impressions"):
            q[key] += value
        elif key == "position":
            q["parts"].append(value)
    if queries:
        block["top_queries"] = _top_queries(queries)
    return block


def _merged_queries(blocks: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "parts": []})
    for b in blocks:
        for q in b.get("top_queries") or []:
            m = merged[q.get("query")]
            m["clicks"] += q.get("clicks", 0) or 0
            m["impressions"] += q.get("impressions", 0) or 0
            if q.get("position"):
                m["parts"].append(q["position"])
    return {k: v for k, v in merged.items() if k}


def _top_queries(queries: dict[str, dict]) -> list[dict]:
    rows = [
        {
            "query": name,
            "clicks": round(v["clicks"]),
            "impressions": round(v["impressions"]),
            "ctr": round(v["clicks"] / v["impressions"] * 100, 2) if v["impressions"] else 0,
            "position": round(sum(v["parts"]) / len(v["parts"]), 1) if v.get("parts") else v.get("position", 0),
        }
        for name, v in queries.items()
    ]
    return sorted(rows, key=lambda r: (r["clicks"], r["impressions"]), reverse=True)[:10]


def _page_clicks(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict[str, dict]:
    """Clicks, impressions and position per page over a window, from stored rows."""
    pages: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "parts": []})
    for (_, page), d in _by_day(_rows(db, client_id, "gsc", start, end, "page")).items():
        if not page:
            continue
        entry = pages[page]
        entry["clicks"] += d.get("clicks", 0)
        entry["impressions"] += d.get("impressions", 0)
        entry["parts"].append((d.get("position", 0), d.get("impressions", 0)))
    return pages


def trending_pages(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date,
                   prev_start: datetime.date, prev_end: datetime.date, limit: int = 10) -> list[dict]:
    """Pages whose search clicks rose against the period just before, biggest
    gain first. Empty when the earlier period has no page data to compare."""
    before = _page_clicks(db, client_id, prev_start, prev_end)
    if not before:
        return []
    rows = []
    for page, now in _page_clicks(db, client_id, start, end).items():
        was = before.get(page, {}).get("clicks", 0.0)
        gain = now["clicks"] - was
        if gain > 0:
            rows.append({
                "page": page,
                "clicks": round(now["clicks"]),
                "prev_clicks": round(was),
                "impressions": round(now["impressions"]),
                "position": round(_weighted_position(now["parts"]), 1),
            })
    rows.sort(key=lambda r: (r["clicks"] - r["prev_clicks"], r["clicks"]), reverse=True)
    return rows[:limit]


def _top_pages(pages: dict[str, tuple[float, float, float]]) -> list[dict]:
    rows = [
        {
            "page": page,
            "clicks": round(clicks),
            "impressions": round(impressions),
            # Pages keep CTR as a percentage, the way the live pull does.
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "position": round(position, 1),
        }
        for page, (clicks, impressions, position) in pages.items()
    ]
    return sorted(rows, key=lambda r: r["clicks"], reverse=True)[:10]


def _ga4_block(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict:
    days = _by_day(_rows(db, client_id, "ga4", start, end))
    if not days:
        return {}
    sessions = sum(d.get("sessions", 0) for d in days.values())
    block: dict[str, Any] = {k: round(sum(d.get(k, 0) for d in days.values()), 2) for k in _GA4_ADDITIVE if k != "organic_sessions"}
    # Daily users cannot be added into a true period total — the same person
    # visits on several days. The sum is the closest stored figure; a cycle
    # pulled live or saved in an earlier report replaces it with the real one.
    block["users"] = round(sum(d.get("users", 0) for d in days.values()))
    block["avg_session_duration"] = (
        sum(d.get("avg_session_duration", 0) * d.get("sessions", 0) for d in days.values()) / sessions if sessions else 0
    )
    for list_key, dimension, name in _GA4_LISTS:
        merged: dict[str, dict] = defaultdict(lambda: {"sessions": 0.0, "users": 0.0, "conversions": 0.0})
        for (_, value), d in _by_day(_rows(db, client_id, "ga4", start, end, dimension)).items():
            if not value:
                continue
            for k in ("sessions", "users", "conversions"):
                merged[value][k] += d.get({"users": "users"}.get(k, k), 0)
        block[list_key] = _top_list(merged, name)

    # Named events, summed over the cycle. These are what the Leads &
    # Conversion figures are built from; the single `conversions` total above
    # cannot be broken back apart into them.
    events: dict[str, float] = defaultdict(float)
    for (_, key, value), amount in _rows(db, client_id, "ga4", start, end, "eventName").items():
        if key == "event_count" and value:
            events[value] += amount
    block["events"] = {k: round(v) for k, v in sorted(events.items(), key=lambda kv: -kv[1])}

    # The comparison tables (channels, countries). Every stored figure is a
    # count or a duration, so rows add straight up; rates are worked out when
    # shown.
    for key, spec in BREAKDOWNS.items():
        fields = breakdown_fields(key)
        rows = breakdown_totals(key, (
            {"name": value, metric: amount}
            for (_, metric, value), amount in _rows(db, client_id, "ga4", start, end, spec["stored_as"]).items()
            if metric in fields
        ))
        if rows:
            block[key] = rows
    return block


def _top_list(merged: dict[str, dict], name: str) -> list[dict]:
    rows = [{name: key, **{k: round(v) for k, v in vals.items()}} for key, vals in merged.items()]
    return sorted(rows, key=lambda r: r.get("sessions", 0), reverse=True)[:10]


def provider_block(db: Session, client_id: uuid.UUID, provider: str, start: datetime.date, end: datetime.date) -> dict:
    """Totals and breakdowns for one provider over a window, from stored rows."""
    if provider == "gsc":
        return _gsc_block(db, client_id, start, end)
    if provider == "ga4":
        return _ga4_block(db, client_id, start, end)
    raise ValueError(provider)


def has_numbers(provider: str, block: Optional[dict]) -> bool:
    if not isinstance(block, dict):
        return False
    keys = {"gsc": ("clicks", "impressions"), "ga4": ("sessions", "users")}.get(provider, ())
    return any((block.get(k) or 0) > 0 for k in keys)


def combine(provider: str, blocks: list[dict]) -> dict:
    """One figure per metric across several cycles, each with its own arithmetic."""
    blocks = [b for b in blocks if isinstance(b, dict) and b]
    if not blocks:
        return {}
    if len(blocks) == 1:
        return dict(blocks[0])

    if provider == "gsc":
        clicks = sum(b.get("clicks", 0) or 0 for b in blocks)
        impressions = sum(b.get("impressions", 0) or 0 for b in blocks)
        pages: dict[str, dict] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "parts": []})
        for b in blocks:
            for p in b.get("top_pages") or []:
                entry = pages[p.get("page")]
                entry["clicks"] += p.get("clicks", 0) or 0
                entry["impressions"] += p.get("impressions", 0) or 0
                entry["parts"].append((p.get("position", 0) or 0, p.get("impressions", 0) or 0))
        return {
            "clicks": round(clicks),
            "impressions": round(impressions),
            "ctr": clicks / impressions if impressions else 0,
            "position": round(_weighted_position([(b.get("position", 0) or 0, b.get("impressions", 0) or 0) for b in blocks]), 2),
            "top_pages": _top_pages({k: (v["clicks"], v["impressions"], _weighted_position(v["parts"])) for k, v in pages.items() if k}),
            # Each cycle's days are distinct, so the series simply joins up.
            "daily": sorted((d for b in blocks for d in (b.get("daily") or [])), key=lambda d: d.get("date") or ""),
            "top_queries": _top_queries(_merged_queries(blocks)),
        }

    sessions = sum(b.get("sessions", 0) or 0 for b in blocks)
    out: dict[str, Any] = {}
    for k in _GA4_ADDITIVE:
        if any(k in b for b in blocks):
            out[k] = round(sum(b.get(k, 0) or 0 for b in blocks), 2)
    # A true multi-month user count needs Google; across cycles the report
    # shows the average month instead of adding people up twice.
    users = [b.get("users", 0) or 0 for b in blocks]
    out["users"] = round(sum(users) / len(users))
    out["avg_session_duration"] = (
        sum((b.get("avg_session_duration", 0) or 0) * (b.get("sessions", 0) or 0) for b in blocks) / sessions if sessions else 0
    )
    for list_key, _, name in _GA4_LISTS:
        merged: dict[str, dict] = defaultdict(lambda: {"sessions": 0.0, "users": 0.0, "conversions": 0.0})
        for b in blocks:
            for row in b.get(list_key) or []:
                key = row.get(name)
                if not key:
                    continue
                for k in ("sessions", "users", "conversions"):
                    merged[key][k] += row.get(k, 0) or 0
        out[list_key] = _top_list(merged, name)

    # Event counts add straight across cycles — each is a distinct action.
    events: dict[str, float] = defaultdict(float)
    for b in blocks:
        for name_, count in (b.get("events") or {}).items():
            events[name_] += count or 0
    out["events"] = {k: round(v) for k, v in sorted(events.items(), key=lambda kv: -kv[1])}

    for key in BREAKDOWNS:
        rows = breakdown_totals(key, (row for b in blocks for row in (b.get(key) or [])))
        if rows:
            out[key] = rows
    return out


def _gbp_in(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict:
    """Business Profile figures pulled for one cycle, summed."""
    totals: dict[str, float] = defaultdict(float)
    for (_, key, _), value in _rows(db, client_id, "gbp", start, end).items():
        totals[key] += value
    return {k: round(v, 2) for k, v in totals.items()}


def _pick(block: dict, keys: tuple[str, ...]) -> dict:
    return {k: block[k] for k in keys if isinstance(block, dict) and block.get(k) is not None}


def _deltas(current: dict, previous: dict) -> dict:
    """Change against the previous period. With nothing stored for it, the
    previous value counts as 0 — the template prints no comparison then."""
    return {
        k: v - (previous.get(k, 0) if isinstance(previous.get(k, 0), (int, float)) else 0)
        for k, v in (current or {}).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _published_snapshots(db: Session, client_id: uuid.UUID) -> dict[datetime.date, dict]:
    """The one-month report behind each month on the sheets, by month. Its
    figures are final, so an older month of a combined report reads them."""
    out = {}
    for month, rep in sheets.month_reports(db, client_id).items():
        data = rep.snapshot or {}
        if ((data.get("period") or {}).get("months") or 1) == 1:
            out[month] = data
    return out


# Sheet rows that are a provider's headline figures.
_SHEET_HEADLINE = {
    "gsc": ("clicks", "impressions", "ctr", "position"),
    "ga4": ("sessions", "users", "engaged_sessions", "conversions", "revenue", "organic_sessions"),
}


def month_on_sheet(db: Session, client_id: uuid.UUID, month: datetime.date) -> dict:
    """A published month's final figures, shaped the way a report keeps them.
    Empty when the month was never published."""
    cells = sheets.month_figures(db, client_id, month)
    if not cells:
        return {}

    def val(sheet: str, key: str):
        return ((cells.get(sheet) or {}).get(key) or {}).get("value")

    out: dict[str, Any] = {"gsc": {}, "ga4": {}, "gbp": {}}
    for provider, keys in _SHEET_HEADLINE.items():
        for key in keys:
            v = val(provider, key)
            if v is not None:
                out[provider][key] = v / 100 if (provider, key) == ("gsc", "ctr") else v
    for key, cell in (cells.get("gbp") or {}).items():
        if cell.get("value") is not None:
            out["gbp"][key] = cell["value"]
    out["leads"] = {k[5:]: c["value"] for k, c in (cells.get("ga4") or {}).items()
                    if k.startswith("lead:") and c.get("value") is not None}
    out["positions"] = {k[3:]: c["value"] for k, c in (cells.get("keywords") or {}).items()
                        if k.startswith("kw:") and c.get("value")}
    checks: dict[str, dict[str, bool]] = {}
    for k, c in (cells.get("ai") or {}).items():
        if k.startswith("prompt:") and c.get("text"):
            pairs = [p.split(":") for p in str(c["text"]).split(",") if ":" in p]
            checks[k[7:]] = {name: flag == "1" for name, flag in pairs}
    out["ai_checks"] = checks
    return out


def _rankings_for(db: Session, client_id: uuid.UUID, before: dict) -> dict:
    """The tracked keywords, each with last month's position from the sheet.
    This month's positions are the report's to fill in."""
    keywords = db.execute(
        select(Keyword).where(Keyword.client_id == client_id, Keyword.is_active.is_(True))
    ).scalars().all()
    positions = before.get("positions") or {}
    rows = []
    for kw in keywords:
        prev = positions.get(str(kw.id))
        rows.append({
            "keyword_id": str(kw.id),
            "term": kw.term,
            "search_volume": kw.search_volume,
            "initial_rank": kw.initial_rank,
            "history": {},
            "change": None,
            "position": None,
            "previous_position": int(prev) if prev else None,
        })
    rows.sort(key=lambda r: (r["previous_position"] or 10_000, r["term"].lower()))
    from app.services.report_composer import ranking_summary
    return {"summary": ranking_summary(rows), "keywords": rows, "months": []}


DEFAULT_ASSISTANTS = ("chatgpt", "google_ai_overview", "gemini", "perplexity")


def _ai_rows_for(db: Session, client_id: uuid.UUID, before: dict) -> tuple[list[dict], list[dict]]:
    """This month's prompt checks, opened with last month's answers so only
    what changed needs a click, and last month's own. This month's stay marked
    unchecked — they print nothing — until the builder confirms or changes them."""
    prompts = db.execute(
        select(AiPrompt).where(AiPrompt.client_id == client_id, AiPrompt.is_active.is_(True))
    ).scalars().all()
    last = before.get("ai_checks") or {}
    rows, earlier = [], []
    for p in prompts:
        checks = last.get(str(p.id))
        for platform in (checks or {name: False for name in DEFAULT_ASSISTANTS}):
            seen = bool((checks or {}).get(platform))
            rows.append({"prompt_id": str(p.id), "prompt": p.prompt_text, "platform": platform,
                         "mentioned": seen, "cited_pages": None, "unchecked": True})
            if checks:
                earlier.append({"prompt_id": str(p.id), "platform": platform, "mentioned": seen})
    return rows, earlier


def _add_cycle_positions(db: Session, client_id: uuid.UUID, rankings: dict, cycles: list[tuple], labels: list[str]) -> None:
    """Each keyword's position in every month of a combined report: older
    months from the sheet, the current one as the report has it."""
    keywords = rankings.get("keywords") or []
    months = [sheets.cycle_month(end) for _, end in cycles[:-1]]
    history = sheets.row_history(db, client_id, "keywords", "kw:", months)
    for kw in keywords:
        hist = history.get(f"kw:{kw.get('keyword_id')}", {})
        positions = {label: (int(hist[m]) if hist.get(m) else None) for m, label in zip(months, labels[:-1])}
        positions[labels[-1]] = kw.get("position")
        kw["positions"] = positions
    rankings["months"] = labels


def _sum_blocks(blocks: list[dict]) -> dict:
    out: dict[str, float] = defaultdict(float)
    for b in blocks:
        for k, v in (b or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] += v
    return dict(out)


def _vs_average(values: list) -> Optional[float]:
    """The last value against the average of the ones before it, in percent.
    None when there is nothing to set it against."""
    *earlier, now = values
    known = [v for v in earlier if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if now is None or not known:
        return None
    avg = sum(known) / len(known)
    return round((now - avg) / avg * 100, 1) if avg else None


def _span_changes(total: dict, blocks: list[dict]) -> tuple[dict, dict]:
    """Each figure's change and "previous" for a several-month report, stored
    so that change ÷ (total − change) — what the slides print — is exactly the
    current month against the earlier months' average. Position is in places."""
    changes, previous = {}, {}
    for k, v in (total or {}).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        series = [(b or {}).get(k) for b in blocks]
        now = series[-1]
        known = [x for x in series[:-1] if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if not isinstance(now, (int, float)) or not known:
            continue
        avg = sum(known) / len(known)
        if k == "position":
            changes[k] = now - avg
            previous[k] = v - changes[k]
        elif avg and now:
            ratio = now / avg                  # current month ÷ the average month
            previous[k] = v / ratio
            changes[k] = v - previous[k]
    return changes, previous


def _span_table_baseline(key: str, combined: list, per_month: list[list]) -> list:
    """For a comparison table over several months: a row per name whose
    figures make each cell's change the current month against the earlier
    months' average for that row (rates included, since both sides scale)."""
    fields = breakdown_fields(key)
    name_key = BREAKDOWNS[key]["name"]
    by_month = [{r.get(name_key): r for r in rows if isinstance(r, dict)} for rows in per_month]
    out = []
    for row in combined or []:
        name = row.get(name_key)
        base = {name_key: name}
        for f in fields:
            series = [(m.get(name) or {}).get(f) for m in by_month]
            now = series[-1]
            known = [float(x) for x in series[:-1] if isinstance(x, (int, float))]
            if not known or not now:
                continue
            avg = sum(known) / len(known)
            if avg:
                base[f] = float(row.get(f) or 0) * avg / float(now)
        if len(base) > 1:
            out.append(base)
    return out


def _short_months(labels: list[str]) -> str:
    """"June 2026", "July 2026", "August 2026" → "Jun–Aug"."""
    names = [l.split(" ")[0][:3] for l in labels]
    return names[0] if len(names) == 1 else f"{names[0]}–{names[-1]}"


def build_report_data(db: Session, client_id: uuid.UUID, anchor_end: datetime.date, months: int,
                      live: Optional[dict] = None, with_page_images: bool = True,
                      start: Optional[datetime.date] = None) -> dict:
    """Everything a report shows, for `months` cycles ending on `anchor_end`.

    Only the current month ever comes from Google: what was pulled for this
    build (see `pulled`) or, when nothing was, `live` — the month's blocks the
    draft already holds. Every earlier month, in the span and in the span it
    is compared with, is the saved (published) report of that month.
    """
    months = max(1, min(int(months or 1), MAX_CYCLES))
    live = live if isinstance(live, dict) else {}
    cycles = report_cycles(anchor_end, months)
    if months == 1 and start and start != cycles[0][0]:
        cycles = [(start, anchor_end)]          # a first report's own period
    labels = cycle_labels(cycles)
    start, end = cycles[0][0], anchor_end
    published = _published_snapshots(db, client_id) if months > 1 else {}

    per_cycle: dict[str, list[dict]] = {"gsc": [], "ga4": [], "gbp": []}
    current: dict[str, dict] = {}
    periods = []
    for (c_start, c_end), label in zip(cycles, labels):
        entry: dict[str, Any] = {"label": label, "range": short_range(c_start, c_end),
                                 "start": c_start.isoformat(), "end": c_end.isoformat()}
        is_current = c_end == anchor_end
        older = published.get(sheets.cycle_month(c_end)) or {}
        for provider in ("gsc", "ga4"):
            if is_current:
                block = provider_block(db, client_id, provider, c_start, c_end)
                if not has_numbers(provider, block) and has_numbers(provider, live.get(provider)):
                    block = dict(live[provider])
                elif has_numbers(provider, live.get(provider)):
                    # Figures Google reports straight (true totals, top lists)
                    # win over ones worked out from the daily rows.
                    block = {**block, **{k: v for k, v in live[provider].items()
                                         if v not in (None, "") and k not in ("daily",)}}
                current[provider] = block
            else:
                block = older.get(provider) or {}
            per_cycle[provider].append(block)
            entry[provider] = _pick(block, PERIOD_KEYS[provider])
        gbp_block = (_gbp_in(db, client_id, c_start, c_end) or dict(live.get("gbp") or {})) if is_current else (older.get("gbp") or {})
        if is_current:
            current["gbp"] = gbp_block
        per_cycle["gbp"].append(gbp_block)
        entry["gbp"] = _pick(gbp_block, PERIOD_KEYS["gbp"])
        periods.append(entry)

    gsc = combine("gsc", per_cycle["gsc"])
    ga4 = combine("ga4", per_cycle["ga4"])
    gbp = _sum_blocks(per_cycle["gbp"]) if months > 1 else dict(per_cycle["gbp"][-1])
    # The comparison is the same length immediately before. One month: last
    # month's published figures (final), else what was pulled with this one.
    # Several months: the saved months before the span, combined the same way
    # — only when every one of them is saved, so a total is never set against
    # a partial one.
    prev_start, prev_end = previous_window(anchor_end, months, start)
    if months == 1:
        previous = {
            "gsc": provider_block(db, client_id, "gsc", prev_start, prev_end),
            "ga4": provider_block(db, client_id, "ga4", prev_start, prev_end),
            "gbp": _gbp_in(db, client_id, prev_start, prev_end),
        }
    else:
        # Several months are compared among themselves (see span_compare
        # below): nothing before the span is needed.
        previous = {"gsc": {}, "ga4": {}, "gbp": {}}
    before = month_on_sheet(db, client_id, sheets.cycle_month(prev_end)) if months == 1 else {}
    for provider in ("gsc", "ga4", "gbp"):
        if before.get(provider):
            previous[provider] = {**previous[provider], **before[provider]}

    ai_rows, ai_before = _ai_rows_for(db, client_id, before)

    def _rate(rows: list) -> float:
        return (sum(1 for r in rows if r.get("mentioned")) / len(rows) * 100) if rows else 0.0

    ai_compare = {
        "rate": 0.0,
        "previous_rate": round(_rate(ai_before), 1),
        "previous_mentioned": sum(1 for r in ai_before if r.get("mentioned")),
        "hasData": bool(ai_before),
    }

    before_pages = {
        (row.get("page") or ""): float(row.get("clicks") or 0)
        for row in ((previous.get("gsc") or {}).get("top_pages") or [])
    }
    for row in (gsc.get("top_pages") or []):
        was = before_pages.get(row.get("page") or "", 0.0)
        row["change"] = (float(row.get("clicks") or 0) - was) if before_pages else None

    for key in BREAKDOWNS:
        if months == 1 and ga4.get(key):
            ga4[f"{key}_previous"] = (previous.get("ga4") or {}).get(key) or []

    if months == 1:
        trending = trending_pages(db, client_id, start, end, prev_start, prev_end)
    else:
        # The span's pages by their clicks over the whole span, each with how
        # its current month compares with its average earlier month.
        trending = []
        for r in gsc.get("top_pages") or []:
            page = r.get("page")
            month_clicks = [next((float(x.get("clicks") or 0) for x in (b or {}).get("top_pages") or [] if x.get("page") == page), None)
                            for b in per_cycle["gsc"]]
            trending.append({"page": page, "clicks": round(float(r.get("clicks") or 0)), "impressions": r.get("impressions"),
                             "position": r.get("position"), "prev_clicks": None,
                             "span_pct": _vs_average(month_clicks)})
    if trending:
        if with_page_images:
            from app.services.page_images import page_images
            found = page_images([r["page"] for r in trending])
            for r in trending:
                if found.get(r["page"]):
                    r["image"] = found[r["page"]]
        gsc["trending_pages"] = trending

    rankings = _rankings_for(db, client_id, before)
    if months > 1:
        _add_cycle_positions(db, client_id, rankings, cycles, labels)

    previous_values = {**_previous_values(previous), "leads": _previous_leads(previous)}
    if before.get("leads"):
        previous_values["leads"] = {**previous_values["leads"],
                                    **{k: v for k, v in before["leads"].items() if k != "total"}}

    kpi_deltas = {p: _deltas(cur, previous[p]) for p, cur in (("gsc", gsc), ("ga4", ga4), ("gbp", gbp))}
    span_label = ""
    if months > 1:
        # Every figure prints the span's total; its change is the current
        # month against the average of the earlier months in the span.
        span_label = f"{labels[-1].split(' ')[0]} vs {_short_months(labels[:-1])} average"
        for p_, total in (("gsc", gsc), ("ga4", ga4), ("gbp", gbp)):
            kpi_deltas[p_], prev_ = _span_changes(total, per_cycle[p_])
            previous_values[p_] = prev_
        for key in BREAKDOWNS:
            if ga4.get(key):
                ga4[f"{key}_previous"] = _span_table_baseline(key, ga4.get(key), [(b or {}).get(key) or [] for b in per_cycle["ga4"]])
        ga4["_span_compare"] = True

    return {
        "gsc": gsc,
        "ga4": ga4,
        "gbp": gbp,
        "rankings": rankings,
        "ai_visibility": ai_rows,
        "ai_compare": ai_compare,
        # Entered in the builder: nothing of this month is recorded anywhere else.
        "links": [],
        "activities": [],
        "screenshots": [],
        "kpi_deltas": kpi_deltas,
        "previous_values": previous_values,
        "periods": periods,
        "period": {
            "months": months,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "labels": labels,
            "label": labels[0] if months == 1 else f"{labels[0]} – {labels[-1]}",
            "range": short_range(start, end),
            "compare": {
                "start": prev_start.isoformat() if months == 1 else cycles[0][0].isoformat(),
                "end": prev_end.isoformat() if months == 1 else cycles[0][1].isoformat(),
                # Several months: the current month against the earlier ones' average.
                "range": short_range(prev_start, prev_end) if months == 1 else span_label,
                "span": months > 1,
                "hasData": (has_numbers("gsc", previous["gsc"]) or has_numbers("ga4", previous["ga4"]) or bool(previous["gbp"]))
                           if months == 1 else any(bool(v) for v in kpi_deltas.values()),
                "published": bool(before),
            },
        },
        # The current month's own blocks, whole: a combined report and the
        # sheet it is published into both need them apart from the totals.
        "live": {p: b for p, b in current.items() if b},
        "provenance": data_provenance(db, client_id, start, end),
    }


def _previous_values(previous: dict) -> dict:
    from app.services.report_composer import comparable_keys
    out = {}
    for section, keys in comparable_keys().items():
        block = previous.get(section) or {}
        out[section] = {k: block[k] for k in keys if isinstance(block.get(k), (int, float)) and block.get(k)}
    return out


def _previous_leads(previous: dict) -> dict:
    """Last period's lead figures, found in its GA4 event names the same way
    this period's are."""
    if not (previous.get("ga4") or {}).get("events"):
        return {}
    from app.services.report_composer import lead_values
    return {k: v for k, v in lead_values({"ga4": previous["ga4"]}).items()}


def previous_window(anchor_end: datetime.date, months: int,
                    start: Optional[datetime.date] = None) -> tuple[datetime.date, datetime.date]:
    """The period a report is compared with: the same length, just before.
    A first report's own period (any length) is compared with as many days
    straight before it."""
    months = max(1, min(int(months or 1), MAX_CYCLES))
    if months == 1 and start and start != cycle_bounds(anchor_end, 0)[0]:
        days = (anchor_end - start).days + 1
        return start - datetime.timedelta(days=days), start - _ONE
    return cycle_bounds(anchor_end, 2 * months - 1)[0], cycle_bounds(anchor_end, months)[1]


def has_comparison(snap: dict) -> bool:
    """Whether a report has anything to compare with. Read from the figures
    themselves — the stored flag is set when the report is made, before a
    later fetch, sheet or typed figure brings last period in."""
    snap = snap or {}
    period = snap.get("period") or {}
    if (period.get("compare") or {}).get("hasData") or (period.get("months") or 1) > 1:
        return True
    def any_number(block) -> bool:
        return any(isinstance(v, (int, float)) and not isinstance(v, bool) and v
                   for v in (block or {}).values())
    if any(any_number(b) for b in (snap.get("previous_values") or {}).values()):
        return True
    if any(any_number(b) for b in (snap.get("kpi_deltas") or {}).values()):
        return True
    if any((k or {}).get("previous_position") for k in ((snap.get("rankings") or {}).get("keywords") or [])):
        return True
    if any_number((snap.get("ga4") or {}).get("lead_overrides_previous")):
        return True
    return bool(((snap.get("ai_compare") or {}) if isinstance(snap.get("ai_compare"), dict) else {}).get("hasData"))


def merge_section(snapshot: dict, fresh: dict, section: str) -> dict:
    """Replace one section of a draft with freshly built data, leaving every
    other section — and its edits — as it was."""
    snap = dict(snapshot or {})
    # Lead figures typed in the builder are not Google's to replace.
    typed = {k: v for k, v in (snap.get("ga4") or {}).items()
             if k in ("lead_overrides", "lead_overrides_previous", "ai_referral_overrides") and v} if section == "ga4" else {}
    for key in SECTION_KEYS[section]:
        snap[key] = fresh.get(key)
    if typed and isinstance(snap.get("ga4"), dict):
        snap["ga4"] = {**snap["ga4"], **typed}
    if section in PERIOD_KEYS:
        previous_values = dict(snap.get("previous_values") or {})
        previous_values[section] = (fresh.get("previous_values") or {}).get(section, {})
        if section == "ga4":
            previous_values["leads"] = (fresh.get("previous_values") or {}).get("leads", {})
        snap["previous_values"] = previous_values
        deltas = dict(snap.get("kpi_deltas") or {})
        deltas[section] = (fresh.get("kpi_deltas") or {}).get(section, {})
        snap["kpi_deltas"] = deltas
        periods = [dict(p) for p in (snap.get("periods") or [])]
        fresh_periods = fresh.get("periods") or []
        if len(periods) == len(fresh_periods):
            for i, fp in enumerate(fresh_periods):
                periods[i][section] = fp.get(section, {})
        else:
            periods = fresh_periods
        snap["periods"] = periods
    if section in ("gsc", "ga4", "gbp"):
        live = dict(snap.get("live") or {})
        if section in (fresh.get("live") or {}):
            live[section] = fresh["live"][section]
        snap["live"] = live
    snap.setdefault("period", fresh.get("period"))
    snap.setdefault("periods", fresh.get("periods"))
    # Fresh figures may bring the first comparison (a report made before its
    # Google source was connected): the report now has something to measure against.
    fresh_compare = ((fresh.get("period") or {}).get("compare") or {})
    if fresh_compare.get("hasData") and isinstance(snap.get("period"), dict):
        period = dict(snap["period"])
        period["compare"] = {**(period.get("compare") or {}), **fresh_compare}
        snap["period"] = period
    return snap
