"""Report periods: 30-day cycles, and reports that combine several of them.

A report covers one or more consecutive 30-day cycles ending on its anchor
date. When a report is generated only the current cycle is pulled from
Google; every older cycle is read from what is already stored, so nothing old
is ever pulled again. Figures are combined with the arithmetic each one
needs — clicks add up, a click-through rate does not.
"""
from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.ai_mention import AiMention
from app.models.enums import MetricSource, ReportStatus
from app.models.keyword import Keyword
from app.models.link import Link
from app.models.metric import Metric
from app.models.ranking import Ranking
from app.models.report_snapshot import ReportSnapshot
from app.models.screenshot import Screenshot

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
    "ai_visibility": ("ai_visibility",),
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


def _no_dimension():
    """A total rather than a breakdown row. Google pulls leave the dimension
    NULL; sheet uploads write an empty string — both mean "no dimension"."""
    return or_(Metric.dimension_key.is_(None), Metric.dimension_key == "")


# ── Cycles ──────────────────────────────────────────────────────────────────

def cycle_bounds(anchor_end: datetime.date, index: int) -> tuple[datetime.date, datetime.date]:
    """Cycle `index` counted back from the anchor; 0 is the cycle ending on it."""
    end = anchor_end - datetime.timedelta(days=CYCLE_DAYS * index)
    return end - datetime.timedelta(days=CYCLE_DAYS - 1), end


def report_cycles(anchor_end: datetime.date, months: int) -> list[tuple[datetime.date, datetime.date]]:
    """The cycles a report of `months` covers, oldest first."""
    return [cycle_bounds(anchor_end, i) for i in reversed(range(months))]


def short_range(start: datetime.date, end: datetime.date) -> str:
    if start.year == end.year:
        return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
    return f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"


def cycle_labels(cycles: list[tuple[datetime.date, datetime.date]]) -> list[str]:
    """Each cycle is named for the month it ends in, as reports always have
    been. Two cycles can end in the same month; those fall back to dates."""
    names = [end.strftime("%B %Y") for _, end in cycles]
    clashes = {n for n in names if names.count(n) > 1}
    return [short_range(s, e) if n in clashes else n for (s, e), n in zip(cycles, names)]


def _exists(db: Session, stmt) -> bool:
    return db.execute(stmt.limit(1)).first() is not None


def cycle_sources(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict[str, bool]:
    """What is already stored for one cycle."""
    month_start = start.replace(day=1)

    def metric(provider: str, lo: datetime.date) -> bool:
        return _exists(db, select(Metric.captured_on).where(
            Metric.client_id == client_id, Metric.provider == provider,
            _no_dimension(), Metric.captured_on >= lo, Metric.captured_on <= end))

    return {
        "gsc": metric("gsc", start),
        "ga4": metric("ga4", start),
        "gbp": metric("gbp", start),
        "rankings": _exists(db, select(Ranking.captured_on).join(Keyword, Keyword.id == Ranking.keyword_id).where(
            Keyword.client_id == client_id, Ranking.captured_on >= start, Ranking.captured_on <= end)),
        "ai_visibility": _exists(db, select(AiMention.id).where(
            AiMention.client_id == client_id, AiMention.month >= month_start, AiMention.month <= end)),
        "links": _exists(db, select(Link.id).where(
            Link.client_id == client_id, Link.month >= month_start, Link.month <= end)),
        "work": _exists(db, select(Activity.id).where(
            Activity.client_id == client_id, Activity.month >= month_start, Activity.month <= end))
        or _exists(db, select(Screenshot.id).where(
            Screenshot.client_id == client_id, Screenshot.month >= month_start, Screenshot.month <= end)),
    }


def anchor_for(db: Session, client_id: uuid.UUID, today: Optional[datetime.date] = None) -> dict:
    """Where the next report's cycle ends, and whether one can be made now.

    new    — no report in the last 30 days; the next cycle ends yesterday
    draft  — this cycle already has a draft; reopen it rather than make another
    locked — this cycle's report is published; the next one is some days away
    """
    yesterday = (today or datetime.date.today()) - _ONE
    last = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
    ).scalars().first()
    if last is not None:
        since = (yesterday - last.end_date).days
        if since < CYCLE_DAYS:
            info = {
                "anchor_end": last.end_date,
                "report_id": str(last.id),
                "months": ((last.snapshot or {}).get("period") or {}).get("months", 1),
            }
            if last.status == ReportStatus.published:
                return {"mode": "locked", "days_remaining": CYCLE_DAYS - since, **info}
            return {"mode": "draft", "days_remaining": CYCLE_DAYS - since, **info}
    return {"mode": "new", "anchor_end": yesterday, "report_id": None, "months": None, "days_remaining": 0}


def timeline(db: Session, client_id: uuid.UUID, anchor_end: datetime.date) -> list[dict]:
    """The cycles a report ending on `anchor_end` can cover, oldest first.

    The current cycle is always offered — it is pulled or entered as the
    report is built. Older cycles are offered back to the first one with
    nothing stored, since a combined report has to be continuous.
    """
    found = []
    for i in range(MAX_CYCLES):
        start, end = cycle_bounds(anchor_end, i)
        sources = cycle_sources(db, client_id, start, end)
        if i > 0 and not any(sources.values()):
            break
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
    """(day, metric_key, dimension_value) → value. Where a day has both an API
    and a hand-entered value, the API one wins, as it does everywhere else."""
    stmt = select(Metric.captured_on, Metric.metric_key, Metric.dimension_value, Metric.value, Metric.source).where(
        Metric.client_id == client_id, Metric.provider == provider,
        Metric.captured_on >= start, Metric.captured_on <= end,
    )
    stmt = stmt.where(_no_dimension()) if dimension is None else stmt.where(Metric.dimension_key == dimension)
    best: dict[tuple, tuple[float, bool]] = {}
    for day, key, dim_value, value, source in db.execute(stmt).all():
        # NULL and "" are one slot, so a month kept both ways is not counted twice.
        slot = (day, key, dim_value or None)
        is_api = source == MetricSource.api or str(source) in ("api", "MetricSource.api")
        if slot not in best or (is_api and not best[slot][1]):
            best[slot] = (float(value or 0), is_api)
    return {slot: v for slot, (v, _) in best.items()}


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
    return block


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
    return out


def _gbp_in(db: Session, client_id: uuid.UUID, start: datetime.date, end: datetime.date) -> dict:
    """Business Profile figures dated inside one cycle (they are stored monthly)."""
    totals: dict[str, float] = defaultdict(float)
    for (_, key, _), value in _rows(db, client_id, "gbp", start, end).items():
        totals[key] += value
    return dict(totals)


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


def _single_cycle_snapshots(db: Session, client_id: uuid.UUID) -> dict[tuple, dict]:
    """Earlier one-cycle reports, by window. Their Google figures came from a
    live pull, so for that cycle they are better than a sum of daily rows."""
    out = {}
    for snap in db.execute(select(ReportSnapshot).where(ReportSnapshot.client_id == client_id)).scalars():
        data = snap.snapshot or {}
        if ((data.get("period") or {}).get("months") or 1) == 1:
            out[(snap.start_date, snap.end_date)] = data
    return out


def _add_cycle_positions(db: Session, rankings: dict, cycles: list[tuple], labels: list[str]) -> None:
    """Each keyword's position at the end of every cycle, for month columns."""
    keywords = rankings.get("keywords") or []
    ids = []
    for kw in keywords:
        try:
            ids.append(uuid.UUID(str(kw.get("keyword_id"))))
        except (ValueError, TypeError):
            continue
    history: dict[str, list[tuple]] = defaultdict(list)
    if ids:
        for kid, day, pos in db.execute(
            select(Ranking.keyword_id, Ranking.captured_on, Ranking.position).where(
                Ranking.keyword_id.in_(ids), Ranking.captured_on >= cycles[0][0], Ranking.captured_on <= cycles[-1][1]
            ).order_by(Ranking.captured_on)
        ).all():
            history[str(kid)].append((day, pos))
    for kw in keywords:
        hist = history.get(str(kw.get("keyword_id")), [])
        positions = {}
        for (start, end), label in zip(cycles, labels):
            inside = [p for d, p in hist if start <= d <= end and p is not None]
            positions[label] = inside[-1] if inside else None
        kw["positions"] = positions
    rankings["months"] = labels


def build_report_data(db: Session, client_id: uuid.UUID, anchor_end: datetime.date, months: int,
                      live: Optional[dict] = None) -> dict:
    """Everything a report shows, for `months` cycles ending on `anchor_end`.

    `live` carries the current cycle's figures straight from Google, when it
    was pulled; every other cycle comes from stored data.
    """
    from app.routes.reports import (
        _resolve_activities, _resolve_ai_visibility, _resolve_links,
        _resolve_metrics, _resolve_rankings, _resolve_screenshots,
    )

    months = max(1, min(int(months or 1), MAX_CYCLES))
    live = live if isinstance(live, dict) else {}
    cycles = report_cycles(anchor_end, months)
    labels = cycle_labels(cycles)
    start, end = cycles[0][0], anchor_end
    earlier = _single_cycle_snapshots(db, client_id) if months > 1 else {}

    per_cycle: dict[str, list[dict]] = {"gsc": [], "ga4": []}
    periods = []
    for (c_start, c_end), label in zip(cycles, labels):
        entry: dict[str, Any] = {"label": label, "range": short_range(c_start, c_end),
                                 "start": c_start.isoformat(), "end": c_end.isoformat()}
        for provider in ("gsc", "ga4"):
            if c_end == anchor_end and has_numbers(provider, live.get(provider)):
                block = live[provider]
            elif has_numbers(provider, (earlier.get((c_start, c_end)) or {}).get(provider)):
                block = earlier[(c_start, c_end)][provider]
            else:
                block = provider_block(db, client_id, provider, c_start, c_end)
            per_cycle[provider].append(block)
            entry[provider] = _pick(block, PERIOD_KEYS[provider])
        entry["gbp"] = _pick(_gbp_in(db, client_id, c_start, c_end), PERIOD_KEYS["gbp"])
        periods.append(entry)

    gsc = combine("gsc", per_cycle["gsc"])
    ga4 = combine("ga4", per_cycle["ga4"])
    gbp = _resolve_metrics(db, client_id, start, end, "gbp")

    # The comparison is the same length immediately before, from stored data.
    prev_end = start - _ONE
    prev_start = prev_end - datetime.timedelta(days=CYCLE_DAYS * months - 1)
    previous = {
        "gsc": provider_block(db, client_id, "gsc", prev_start, prev_end),
        "ga4": provider_block(db, client_id, "ga4", prev_start, prev_end),
        "gbp": _resolve_metrics(db, client_id, prev_start, prev_end, "gbp"),
    }

    rankings = _resolve_rankings(db, client_id, start, end, prev_start, prev_end)
    if months > 1:
        _add_cycle_positions(db, rankings, cycles, labels)

    return {
        "gsc": gsc,
        "ga4": ga4,
        "gbp": gbp,
        "rankings": rankings,
        "ai_visibility": _resolve_ai_visibility(db, client_id, start, end),
        "links": _resolve_links(db, client_id, start, end),
        "activities": _resolve_activities(db, client_id, start, end),
        "screenshots": _resolve_screenshots(db, client_id, start, end),
        "kpi_deltas": {p: _deltas(cur, previous[p]) for p, cur in (("gsc", gsc), ("ga4", ga4), ("gbp", gbp))},
        "periods": periods,
        "period": {
            "months": months,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "labels": labels,
            "label": labels[0] if months == 1 else f"{labels[0]} – {labels[-1]}",
            "range": short_range(start, end),
            "compare": {
                "start": prev_start.isoformat(),
                "end": prev_end.isoformat(),
                "range": short_range(prev_start, prev_end),
                "hasData": has_numbers("gsc", previous["gsc"]) or has_numbers("ga4", previous["ga4"]) or bool(previous["gbp"]),
            },
        },
        "live": {p: live[p] for p in ("gsc", "ga4") if has_numbers(p, live.get(p))},
    }


def merge_section(snapshot: dict, fresh: dict, section: str) -> dict:
    """Replace one section of a draft with freshly built data, leaving every
    other section — and its edits — as it was."""
    snap = dict(snapshot or {})
    for key in SECTION_KEYS[section]:
        snap[key] = fresh.get(key)
    if section in PERIOD_KEYS:
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
    if section in ("gsc", "ga4"):
        live = dict(snap.get("live") or {})
        if section in (fresh.get("live") or {}):
            live[section] = fresh["live"][section]
        snap["live"] = live
    snap.setdefault("period", fresh.get("period"))
    snap.setdefault("periods", fresh.get("periods"))
    return snap
