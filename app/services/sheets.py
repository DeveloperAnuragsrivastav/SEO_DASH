"""Month-on-month sheets: a client's final figures, one column per month.

Nothing is written here while a report is being built. The draft keeps its
own figures inside the report; publishing it writes that month's column into
every sheet in one go. From then on the column is the agency's record of the
month — the next report reads "last month" from it, and only a super admin
may correct a figure.
"""
from __future__ import annotations

import datetime
import uuid
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

# The sheets, in sidebar order. `groups` are the row groups in the order the
# sheet prints them; a row's group is stored with it.
SHEETS: list[dict] = [
    {"key": "gsc", "name": "Search Console", "groups": ["", "Top pages · clicks", "Top queries · clicks"]},
    {"key": "ga4", "name": "Google Analytics",
     "groups": ["", "Leads", "Channels · sessions", "Countries · sessions", "AI assistant referrals · sessions"]},
    {"key": "gbp", "name": "Business Profile", "groups": ["", "Impressions"]},
    {"key": "keywords", "name": "Keywords", "groups": ["Summary", ""]},
    {"key": "ai", "name": "AI Visibility", "groups": ["Summary", "By assistant · mentions", "Prompts"]},
    {"key": "links", "name": "Backlinks", "groups": ["", "By activity"]},
    {"key": "work", "name": "On-Site SEO", "groups": [""]},
]
SHEET_KEYS = [s["key"] for s in SHEETS]

# How each figure prints. Rows not listed take their group's format, then "int".
FORMATS: dict[tuple[str, str], str] = {
    ("gsc", "ctr"): "percent",
    ("gsc", "position"): "position",
    ("ga4", "revenue"): "money",
    ("ga4", "avg_session_duration"): "seconds",
    ("ai", "score"): "percent",
    # Keyword bands: more in the middle bands is neither good nor bad.
    ("keywords", "sum:11_20"): "count",
    ("keywords", "sum:21_30"): "count",
    ("keywords", "sum:31_40"): "count",
    ("keywords", "sum:41_50"): "count",
    ("keywords", "sum:51_100"): "count",
    ("keywords", "sum:none"): "int_low",
    ("keywords", "sum:declined"): "int_low",
    ("gsc", "position"): "position",
}
GROUP_FORMATS: dict[tuple[str, str], str] = {
    ("keywords", ""): "position",
    ("ai", "Prompts"): "checks",
}

GBP_LABELS = {
    "calls": "Calls",
    "chat_clicks": "Chat clicks",
    "direction_requests": "Direction requests",
    "website_clicks": "Website clicks",
    "bookings": "Bookings",
    "impressions_desktop_maps": "Desktop · Maps",
    "impressions_desktop_search": "Desktop · Search",
    "impressions_mobile_maps": "Mobile · Maps",
    "impressions_mobile_search": "Mobile · Search",
}

AI_NAMES = {
    "chatgpt": "ChatGPT", "google_ai_overview": "AI Overview", "ai_mode": "AI Mode", "gemini": "Gemini",
    "perplexity": "Perplexity", "claude": "Claude", "grok": "Grok",
}


def month_of(day: datetime.date) -> datetime.date:
    return datetime.date(day.year, day.month, 1)


def cycle_month(end: datetime.date) -> datetime.date:
    """The sheet column a report period ending on `end` is filed under.

    Reports run on the same date every month (see report_period.cycle_bounds),
    from the day after the last one ended. A period from the 1st is its own
    month. One starting by the 15th mostly falls in the month it starts in
    (5 Sep – 4 Oct is September's); one starting later mostly falls in the
    month it ends in (20 Sep – 19 Oct is October's). The rule depends only on
    the start day, so consecutive periods always get consecutive months.
    """
    start_day = (end + datetime.timedelta(days=1)).day
    if start_day == 1 or start_day >= 16:
        return month_of(end)
    return month_of(month_of(end) - datetime.timedelta(days=1))


def report_month(report) -> datetime.date:
    """The month a report is filed under on the sheets."""
    return cycle_month(report.end_date)


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _current_block(snapshot: dict, provider: str) -> dict:
    """The report month's own figures. A report spanning several months keeps
    the combined figures as its blocks and the last month's under `live`."""
    months = ((snapshot.get("period") or {}).get("months")) or 1
    if months > 1:
        return ((snapshot.get("live") or {}).get(provider)) or {}
    return snapshot.get(provider) or {}


# ── Report → cells ──────────────────────────────────────────────────────────

def cells_from_report(snapshot: dict) -> list[dict]:
    """Every sheet row a report's month contributes: {sheet, row_key, grp, label, value, text}."""
    from app.services import report_composer as composer
    from app.services import slide_deck

    out: list[dict] = []

    def add(sheet: str, key: str, label: str, value: Any = None, grp: str = "", text: Optional[str] = None) -> None:
        v = _num(value)
        if v is None and not text:
            return
        out.append({"sheet": sheet, "row_key": key, "grp": grp, "label": label, "value": v, "text": text})

    # Search Console
    gsc = _current_block(snapshot, "gsc")
    add("gsc", "clicks", "Clicks", gsc.get("clicks"))
    add("gsc", "impressions", "Impressions", gsc.get("impressions"))
    ctr = _num(gsc.get("ctr"))
    if ctr is not None:
        add("gsc", "ctr", "CTR", ctr * 100 if ctr <= 1 else ctr)
    add("gsc", "position", "Average position", gsc.get("position"))
    for row in (gsc.get("top_pages") or [])[:10]:
        if row.get("page"):
            add("gsc", f"page:{row['page']}", row["page"], row.get("clicks"), "Top pages · clicks")
    for row in (gsc.get("top_queries") or [])[:10]:
        if row.get("query"):
            add("gsc", f"query:{row['query']}", row["query"], row.get("clicks"), "Top queries · clicks")

    # Analytics
    ga4 = _current_block(snapshot, "ga4")
    for key, label in (("sessions", "Sessions"), ("users", "Users"), ("engaged_sessions", "Engaged sessions"),
                       ("conversions", "Conversions"), ("revenue", "Revenue"),
                       ("organic_sessions", "Organic sessions")):
        add("ga4", key, label, ga4.get(key))
    snap_for_leads = {**snapshot, "ga4": {**(snapshot.get("ga4") or {}), **({"events": ga4.get("events")} if ga4.get("events") else {})}}
    leads = composer.lead_values(snap_for_leads)
    if ((snapshot.get("period") or {}).get("months") or 1) > 1 and snapshot.get("month_leads"):
        leads = {k: float(v or 0) for k, v in snapshot["month_leads"].items()}
    names = {m["key"]: m["label"] for m in composer.LEAD_KEYS}
    for key, value in leads.items():
        add("ga4", f"lead:{key}", names.get(key, key), value or 0, "Leads")
    typed_total = ((snapshot.get("ga4") or {}).get("lead_overrides") or {}).get("total")
    if ((snapshot.get("period") or {}).get("months") or 1) > 1:
        typed_total = None
    total = _num(typed_total) if typed_total is not None else sum(leads.values())
    add("ga4", "lead:total", "Total leads", total or 0, "Leads")
    for row in ga4.get("channels") or []:
        if row.get("channel"):
            add("ga4", f"channel:{row['channel']}", row["channel"], row.get("sessions"), "Channels · sessions")
    countries = ga4.get("countries_detail") or ga4.get("countries") or []
    for row in countries[:15]:
        if row.get("country"):
            add("ga4", f"country:{row['country']}", row["country"], row.get("sessions"), "Countries · sessions")
    referral = slide_deck.ai_referral_traffic({**ga4, "ai_referral_overrides": (snapshot.get("ga4") or {}).get("ai_referral_overrides")})
    for engine in referral.get("engines") or []:
        add("ga4", f"ai:{engine['name']}", engine["name"], engine["sessions"], "AI assistant referrals · sessions")

    # Business Profile
    gbp = _current_block(snapshot, "gbp")
    order = list(GBP_LABELS)
    for key, value in sorted(gbp.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order)):
        if key.startswith("impressions_"):
            add("gbp", key, GBP_LABELS.get(key, key.replace("_", " ").title()), value, "Impressions")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            add("gbp", key, GBP_LABELS.get(key, key.replace("_", " ").capitalize()), value)

    # Keywords: each position, and the bands the slide counts
    rankings = snapshot.get("rankings") or {}
    for kw in rankings.get("keywords") or []:
        ident = kw.get("keyword_id")
        if ident and kw.get("term") and kw.get("position"):
            add("keywords", f"kw:{ident}", kw["term"], kw.get("position"))
    # The same seven bands the Ranking Summary slide prints, typed counts included.
    if rankings.get("keywords"):
        kws = rankings.get("keywords") or []
        bands = composer.rank_bands_final(kws, rankings.get("summary_overrides"))
        names = {"top10": "Top 10", "11_20": "11–20", "21_30": "21–30", "31_40": "31–40",
                 "41_50": "41–50", "51_100": "51–100", "none": "Not in top 100"}
        for key in composer.rank_band_keys():
            out.append({"sheet": "keywords", "row_key": f"sum:{key}", "grp": "Summary", "label": names.get(key, key),
                        "value": float((bands.get(key) or {}).get("now") or 0), "text": None})
        moves = composer.ranking_summary(kws, rankings.get("summary_overrides"))
        for key, label in (("improved", "Improved"), ("declined", "Declined")):
            out.append({"sheet": "keywords", "row_key": f"sum:{key}", "grp": "Summary", "label": label,
                        "value": float(moves.get(key) or 0), "text": None})

    # AI visibility
    rows = [r for r in (snapshot.get("ai_visibility") or []) if isinstance(r, dict)]
    summary_ai = slide_deck.ai_summary(snapshot)
    for key, label in (("score", "AI visibility score"), ("mentions", "Total mentions"), ("cited", "Cited pages")):
        out.append({"sheet": "ai", "row_key": key, "grp": "Summary", "label": label,
                    "value": float(summary_ai.get(key) or 0), "text": None})
    for engine in summary_ai.get("engines") or []:
        add("ai", f"engine:{engine['key']}", engine["name"], engine["mentions"], "By assistant · mentions")
    by_prompt: dict[str, dict] = {}
    for r in rows:
        pid = str(r.get("prompt_id") or "")
        if not pid:
            continue
        entry = by_prompt.setdefault(pid, {"label": r.get("prompt") or r.get("prompt_text") or "", "checks": {}})
        entry["checks"][str(r.get("platform") or "")] = bool(r.get("mentioned"))
        if not entry["label"]:
            entry["label"] = r.get("prompt") or ""
    for pid, entry in by_prompt.items():
        checks = entry["checks"]
        out.append({"sheet": "ai", "row_key": f"prompt:{pid}", "grp": "Prompts", "label": entry["label"] or "Prompt",
                    "value": float(sum(1 for v in checks.values() if v)),
                    "text": ",".join(f"{k}:{int(v)}" for k, v in checks.items())})

    # Backlinks: how many of each kind this month
    counts: dict[str, list] = {}
    for link in snapshot.get("links") or []:
        kind = str(link.get("activity_type") or "Other").strip() or "Other"
        entry = counts.setdefault(kind.lower(), [kind, 0.0])
        entry[1] += _num(link.get("count")) or 1
    out.append({"sheet": "links", "row_key": "total", "grp": "", "label": "Total links",
                "value": float(sum(c for _, c in counts.values())), "text": None})
    if counts:
        for key, (label, count) in counts.items():
            add("links", f"act:{key}", label, count, "By activity")

    # On-site work
    for act in snapshot.get("activities") or []:
        kind = str(act.get("activity_type") or "").strip()
        if kind:
            add("work", f"act:{kind.lower()}", kind, _num(act.get("count")) or 0, "", (act.get("notes") or None))

    # One row per key and sheet: the last one written wins.
    unique: dict[tuple, dict] = {}
    for c in out:
        unique[(c["sheet"], c["row_key"])] = c
    return list(unique.values())


# ── Publishing ──────────────────────────────────────────────────────────────

def _remap_items(snapshot: dict, old: str, new: str) -> None:
    items = snapshot.get("included_items")
    if isinstance(items, dict):
        snapshot["included_items"] = {k.replace(old, new): v for k, v in items.items()}


def materialize(db: Session, client_id: uuid.UUID, snapshot: dict) -> None:
    """Keywords and prompts added in the builder become tracked ones, and each
    keyword's starting position is kept on it, now the report is final."""
    from app.models.ai_prompt import AiPrompt
    from app.models.keyword import Keyword

    today = datetime.date.today()
    rankings = dict(snapshot.get("rankings") or {})
    keywords = []
    for kw in rankings.get("keywords") or []:
        kw = dict(kw)
        term = " ".join(str(kw.get("term") or "").split())
        ident = str(kw.get("keyword_id") or "")
        row = None
        if ident and not ident.startswith("new-"):
            try:
                row = db.get(Keyword, uuid.UUID(ident))
            except ValueError:
                row = None
        if row is None and term:
            row = db.execute(select(Keyword).where(
                Keyword.client_id == client_id, func.lower(Keyword.term) == term.lower())).scalars().first()
        if row is None and term:
            row = Keyword(client_id=client_id, term=term, added_at=today, is_active=True)
            db.add(row)
            db.flush()
        if row is not None and row.client_id == client_id:
            row.is_active = True
            if kw.get("initial_rank"):
                row.initial_rank = int(kw["initial_rank"])
            if kw.get("search_volume") is not None:
                row.search_volume = kw.get("search_volume")
            if ident != str(row.id):
                _remap_items(snapshot, f"kw.{ident}", f"kw.{row.id}")
                kw["keyword_id"] = str(row.id)
        keywords.append(kw)
    if keywords:
        rankings["keywords"] = keywords
        snapshot["rankings"] = rankings

    rows = []
    made: dict[str, str] = {}
    for r in snapshot.get("ai_visibility") or []:
        r = dict(r)
        pid = str(r.get("prompt_id") or "")
        if pid.startswith("new-") or not pid:
            if pid not in made:
                text_ = " ".join(str(r.get("prompt") or "").split())
                prompt = db.execute(select(AiPrompt).where(
                    AiPrompt.client_id == client_id, func.lower(AiPrompt.prompt_text) == text_.lower())).scalars().first() if text_ else None
                if prompt is None and text_:
                    prompt = AiPrompt(client_id=client_id, prompt_text=text_, added_at=today, is_active=True)
                    db.add(prompt)
                    db.flush()
                made[pid] = str(prompt.id) if prompt else pid
                if prompt and pid:
                    _remap_items(snapshot, f"ai_visibility.{pid}.", f"ai_visibility.{prompt.id}.")
            r["prompt_id"] = made[pid]
        rows.append(r)
    if rows:
        snapshot["ai_visibility"] = rows


def publish(db: Session, report, user_id: Optional[uuid.UUID]) -> int:
    """Write the report's month into every sheet. Returns the cells written."""
    from app.models.sheet_cell import SheetCell

    snapshot = dict(report.snapshot or {})
    materialize(db, report.client_id, snapshot)
    report.snapshot = snapshot

    month = report_month(report)
    cells = cells_from_report(snapshot)
    db.execute(delete(SheetCell).where(SheetCell.client_id == report.client_id, SheetCell.month == month))
    ordinal: dict[str, int] = defaultdict(int)
    now = datetime.datetime.now(datetime.timezone.utc)
    for c in cells:
        ordinal[c["sheet"]] += 1
        db.add(SheetCell(
            client_id=report.client_id, sheet=c["sheet"], row_key=c["row_key"][:500], month=month,
            grp=c["grp"], label=str(c["label"])[:500], ordinal=ordinal[c["sheet"]],
            value=c["value"], text=c["text"], report_id=report.id, updated_at=now, updated_by=user_id,
        ))
    return len(cells)


# ── Reading ─────────────────────────────────────────────────────────────────

def month_reports(db: Session, client_id: uuid.UUID) -> dict:
    """The report behind each month on the sheets. A report made a draft again
    still owns its month — the sheets keep its published figures until it is
    published again — so a combined report reads that month from it."""
    from app.models.report_snapshot import ReportSnapshot
    from app.models.sheet_cell import SheetCell
    owners = dict(db.execute(
        select(SheetCell.month, SheetCell.report_id).where(
            SheetCell.client_id == client_id, SheetCell.report_id.is_not(None)).distinct()
    ).all())
    out = {}
    for month, rid in owners.items():
        rep = db.get(ReportSnapshot, rid)
        if rep is not None:
            out[month] = rep
    return out


def published_months(db: Session, client_id: uuid.UUID) -> list[datetime.date]:
    from app.models.sheet_cell import SheetCell
    return list(db.execute(
        select(SheetCell.month).where(SheetCell.client_id == client_id).distinct().order_by(SheetCell.month)
    ).scalars())


def month_figures(db: Session, client_id: uuid.UUID, month: datetime.date) -> dict[str, dict[str, dict]]:
    """One month's column of every sheet: {sheet: {row_key: {value, text, label}}}."""
    from app.models.sheet_cell import SheetCell
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for c in db.execute(select(SheetCell).where(SheetCell.client_id == client_id, SheetCell.month == month)).scalars():
        out[c.sheet][c.row_key] = {"value": float(c.value) if c.value is not None else None, "text": c.text, "label": c.label}
    return dict(out)


def row_history(db: Session, client_id: uuid.UUID, sheet: str, prefix: str,
                months: list[datetime.date]) -> dict[str, dict[datetime.date, Optional[float]]]:
    """Each row's figure in the given months, for rows whose key starts with `prefix`."""
    from app.models.sheet_cell import SheetCell
    out: dict[str, dict] = defaultdict(dict)
    if not months:
        return {}
    for key, month, value in db.execute(
        select(SheetCell.row_key, SheetCell.month, SheetCell.value).where(
            SheetCell.client_id == client_id, SheetCell.sheet == sheet,
            SheetCell.row_key.startswith(prefix), SheetCell.month.in_(months))
    ).all():
        out[key][month] = float(value) if value is not None else None
    return dict(out)


def fmt_of(sheet: str, row_key: str, grp: str) -> str:
    return FORMATS.get((sheet, row_key)) or GROUP_FORMATS.get((sheet, grp)) or "int"


def sheet_view(db: Session, client_id: uuid.UUID, sheet: str) -> dict:
    """A sheet as rows × months, grouped as it prints."""
    from app.models.ai_prompt import AiPrompt
    from app.models.enums import ReportStatus
    from app.models.keyword import Keyword
    from app.models.report_snapshot import ReportSnapshot
    from app.models.sheet_cell import SheetCell

    spec = next(s for s in SHEETS if s["key"] == sheet)
    cells = db.execute(
        select(SheetCell).where(SheetCell.client_id == client_id, SheetCell.sheet == sheet)
        .order_by(SheetCell.month.desc(), SheetCell.ordinal)
    ).scalars().all()
    months = sorted({c.month for c in cells})
    # The report each month was published from, to open it from the column head.
    published = db.execute(select(ReportSnapshot).where(
        ReportSnapshot.client_id == client_id, ReportSnapshot.status == ReportStatus.published)).scalars().all()
    reports = {cycle_month(r.end_date): str(r.id) for r in published}
    # A column is named by its period: "Sep 2026" for a calendar month, its
    # dates ("5 Sep – 4 Oct") for a client whose reports start on another day.
    from app.services.report_period import period_name
    period_of = {cycle_month(r.end_date): (r.start_date, r.end_date) for r in published}

    def column_label(m: datetime.date) -> str:
        span = period_of.get(m)
        name = period_name(*span) if span and span[0] else None
        return m.strftime("%b %Y") if not name or name == span[1].strftime("%B %Y") else name

    rows: dict[str, dict] = {}
    for c in cells:  # newest month first, so a row takes its latest name and place
        row = rows.get(c.row_key)
        if row is None:
            row = rows[c.row_key] = {
                "key": c.row_key, "label": c.label, "group": c.grp, "format": fmt_of(sheet, c.row_key, c.grp),
                "order": (months.index(c.month) * -1, c.ordinal), "cells": {},
            }
        row["cells"][c.month.isoformat()] = {
            "value": float(c.value) if c.value is not None else None, "text": c.text, "edited": c.edited,
        }

    extra_cols: list[dict] = []
    if sheet == "keywords":
        extra_cols = [{"key": "initial", "label": "Initial"}, {"key": "sv", "label": "Search volume"}]
        for kw in db.execute(select(Keyword).where(Keyword.client_id == client_id, Keyword.is_active.is_(True))).scalars():
            key = f"kw:{kw.id}"
            row = rows.setdefault(key, {"key": key, "label": kw.term, "group": "", "format": "position",
                                        "order": (1, 0), "cells": {}})
            row["label"] = kw.term
            row["extra"] = {"initial": kw.initial_rank, "sv": kw.search_volume}
    if sheet == "ai":
        texts = {f"prompt:{p}": t for p, t in db.execute(
            select(AiPrompt.id, AiPrompt.prompt_text).where(AiPrompt.client_id == client_id)).all()}
        for key, row in rows.items():
            if key in texts:
                row["label"] = texts[key]

    groups = []
    order = spec["groups"] + sorted({r["group"] for r in rows.values()} - set(spec["groups"]))
    for g in order:
        members = [r for r in rows.values() if r["group"] == g]
        if not members:
            continue
        if sheet == "keywords" and g == "":
            # Best position in the latest month first, as a rank tracker reads.
            last = months[-1].isoformat() if months else None
            members.sort(key=lambda r: ((r["cells"].get(last) or {}).get("value") or 10_000, r["label"].lower()))
        else:
            members.sort(key=lambda r: r["order"])
        for r in members:
            r.pop("order", None)
        groups.append({"name": g, "rows": members})

    return {
        "sheet": sheet,
        "name": spec["name"],
        "months": [{"key": m.isoformat(), "label": column_label(m), "report": reports.get(m)} for m in months],
        "extraColumns": extra_cols,
        "groups": groups,
    }


def month_details(db: Session, client_id: uuid.UUID, sheet: str, month: datetime.date) -> list[dict]:
    """The individual entries behind a month's counts, from the published report."""
    from app.models.report_snapshot import ReportSnapshot
    from app.models.enums import ReportStatus
    report = next((r for r in db.execute(select(ReportSnapshot).where(
        ReportSnapshot.client_id == client_id, ReportSnapshot.status == ReportStatus.published)).scalars()
        if cycle_month(r.end_date) == month), None)
    if report is None:
        return []
    snap = report.snapshot or {}
    if sheet == "links":
        return [{"name": l.get("activity_type") or "", "url": l.get("url") or "", "count": l.get("count") or 1}
                for l in snap.get("links") or []]
    if sheet == "work":
        return [{"name": a.get("activity_type") or "", "count": a.get("count") or 0, "notes": a.get("notes") or ""}
                for a in snap.get("activities") or []]
    return []


def edit_cell(db: Session, client_id: uuid.UUID, sheet: str, row_key: str, month: datetime.date,
              value: Optional[float], text: Optional[str], user_id: Optional[uuid.UUID]) -> dict:
    """A super admin's correction to a published month. The month must be
    published; a row missing from it takes its name from another month."""
    from app.models.sheet_cell import SheetCell
    if month not in published_months(db, client_id):
        raise ValueError("That month has not been published yet.")
    cell = db.get(SheetCell, (client_id, sheet, row_key, month))
    if cell is None:
        other = db.execute(select(SheetCell).where(
            SheetCell.client_id == client_id, SheetCell.sheet == sheet, SheetCell.row_key == row_key)).scalars().first()
        label, grp = (other.label, other.grp) if other else (None, "")
        if label is None and sheet == "keywords" and row_key.startswith("kw:"):
            from app.models.keyword import Keyword
            kw = db.get(Keyword, uuid.UUID(row_key[3:]))
            label = kw.term if kw and kw.client_id == client_id else None
        if label is None:
            raise ValueError("Unknown row.")
        cell = SheetCell(client_id=client_id, sheet=sheet, row_key=row_key, month=month, grp=grp, label=label, ordinal=999)
        db.add(cell)
    cell.value = value
    if text is not None:
        cell.text = text or None
    cell.edited = True
    cell.updated_by = user_id
    cell.updated_at = datetime.datetime.now(datetime.timezone.utc)
    return {"value": float(cell.value) if cell.value is not None else None, "text": cell.text, "edited": True}
