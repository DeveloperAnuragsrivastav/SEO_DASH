"""Turns a report snapshot into the values the slide deck prints.

The deck reads as a narrative — a cover figure, a scorecard, a ranking
journey — rather than as one table per data source. Those shapes are not in
the snapshot, so they are derived here, once, and handed to the template
ready to draw. The template stays a layout; this module holds the arithmetic.
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

# The four Business Profile impression metrics, and how to name them once a
# client sees them. Google splits by surface and device; the report shows the
# same split because it tells the client where to invest.
GBP_DISCOVERY = [
    ("impressions_mobile_search", "disc.search_mobile"),
    ("impressions_desktop_search", "disc.search_desktop"),
    ("impressions_mobile_maps", "disc.maps_mobile"),
    ("impressions_desktop_maps", "disc.maps_desktop"),
]

# The actions a Business Profile can produce, in the order they matter.
GBP_ACTIONS = [
    ("calls", "gbp.calls"),
    ("chat_clicks", "gbp.chat"),
    ("website_clicks", "gbp.website"),
    ("direction_requests", "gbp.directions"),
    ("bookings", "gbp.bookings"),
]

# ── Leads & Conversion ─────────────────────────────────────────────────────
#
# GA4 event names are chosen by whoever set the property up, so there is no
# fixed list to read. Each figure below matches on the words that name the
# action rather than on one exact event, and anything matching none of them
# still shows under its own name further down the slide. A property using
# house names is covered by hand-entering the figure instead.
# Events GA4 collects on its own. A scroll or a page view is not an enquiry,
# and listing them beside real conversions would overstate the month badly.
GA4_AUTOMATIC_EVENTS = {
    "page_view", "session_start", "first_visit", "first_open", "user_engagement",
    "scroll", "click", "view_search_results", "file_download", "video_start",
    "video_progress", "video_complete", "form_start", "site_search",
}

LEAD_FIGURES: list[tuple[str, tuple[str, ...]]] = [
    ("lead.thank_you", ("thank_you", "thankyou", "thank-you", "form_submit",
                        "generate_lead", "contact_form", "lead_form")),
    ("lead.email", ("email", "mailto")),
    ("lead.phone", ("phone", "call", "tel_click", "click_to_call")),
    ("lead.transactions", ("purchase", "transaction", "checkout_complete", "order")),
]


def _n(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: Any) -> str:
    """A count as a reader expects it: whole, with thousand separators.

    Nobody made 721.82 calls — that decimal is an artefact of summing daily
    rows, not a fact about the month.
    """
    return f"{int(round(_n(value))):,}"


def _pct_change(current: Any, change: Any) -> Optional[float]:
    """Percentage change, or None when there is no earlier figure to compare."""
    cur, chg = _n(current), _n(change)
    prev = cur - chg
    if prev <= 0:
        return None
    return round(chg / prev * 100, 1)


# ── Rankings ────────────────────────────────────────────────────────────────

def ranking_journey(keywords: list[dict], months: list[str]) -> list[dict]:
    """Average tracked position for each month the report covers.

    Only keywords actually ranking that month count — averaging in the ones
    that were nowhere would make a month look worse the more terms are added.
    """
    out = []
    for month in months:
        found = [
            _n(k.get("positions", {}).get(month))
            for k in keywords
            if k.get("positions", {}).get(month)
        ]
        if found:
            out.append({"label": month, "avg": round(sum(found) / len(found), 1)})
    return out


def ranking_bands(keywords: list[dict], months: list[str]) -> list[dict]:
    """How many tracked terms reached the top 10 and the top 3, per month."""
    out = []
    for month in months:
        positions = [
            _n(k.get("positions", {}).get(month))
            for k in keywords
            if k.get("positions", {}).get(month)
        ]
        out.append({
            "label": month,
            "top10": sum(1 for p in positions if 0 < p <= 10),
            "top3": sum(1 for p in positions if 0 < p <= 3),
        })
    return out


def latest_positions(keywords: list[dict], months: list[str]) -> list[float]:
    """Each keyword's position in the most recent month it was measured.

    Rows in the comparative structure do not all carry a flat `position`, so
    the month map — the same source the ranking table reads — is the only
    dependable one. A term missing from every month counts as zero, which
    keeps it out of any "on page one" tally.
    """
    out = []
    for k in keywords:
        positions = k.get("positions") or {}
        found = 0.0
        for month in reversed(months or list(positions)):
            if _n(positions.get(month)):
                found = _n(positions.get(month))
                break
        out.append(found or _n(k.get("position")))
    return out


def starting_positions(keywords: list[dict], months: list[str]) -> dict:
    """Where a newly tracked keyword set actually stands on day one.

    A first report has one month of positions, so a trend chart has nothing to
    plot and a band chart draws a column of zeros. What a client genuinely
    wants to know at this point is simpler: how many terms are being watched,
    how many have surfaced at all, and how close the best of them is.
    """
    positions = [p for p in latest_positions(keywords, months) if p > 0]
    bands = [
        ("Top 10", sum(1 for p in positions if p <= 10)),
        ("11 – 20", sum(1 for p in positions if 10 < p <= 20)),
        ("21 – 50", sum(1 for p in positions if 20 < p <= 50)),
        ("Beyond 50", sum(1 for p in positions if p > 50)),
        ("Not yet showing", len(keywords) - len(positions)),
    ]
    return {
        "tracked": len(keywords),
        "ranking": len(positions),
        "best": int(min(positions)) if positions else None,
        "bands": [{"name": n, "count": c} for n, c in bands if c],
    }


# The bands the ranking summary reports against, and where each one ends.
POSITION_BANDS = [
    ("band.top10", 1, 10),
    ("band.11_20", 11, 20),
    ("band.21_30", 21, 30),
    ("band.31_40", 31, 40),
    ("band.41_50", 41, 50),
    ("band.51_100", 51, 100),
    ("band.none", 101, 10_000),
]


def position_bands(keywords: list[dict], months: list[str], t=None, overrides: Optional[dict] = None) -> dict:
    """How many tracked terms sat in each band, month by month and at the start.

    This is the shape the approved report uses: bands down the side, the
    months across, and the position every keyword began at as the last column
    — so a reader sees the whole journey in one table rather than a trend line
    that only says where the average is.
    """
    from app.services.report_text import resolver
    t = t or resolver(None)

    # "Initial" is the column's printed name; INITIAL is how the code refers to
    # it, so renaming the column in the builder cannot break the lookup below.
    INITIAL = "\x00initial"
    initial_label = t("rank.initial")
    # Newest month first, with where every term started as the last column.
    columns = list(reversed(months)) + [INITIAL]

    def count(band_lo: int, band_hi: int, column: str) -> int:
        n = 0
        for k in keywords:
            if column == INITIAL:
                pos = _n(k.get("initial_rank"))
            else:
                pos = _n((k.get("positions") or {}).get(column))
            # A term that was never seen is outside the hundred, not at zero.
            if not pos:
                pos = 10_000 if band_hi >= 10_000 else 0
            if pos and band_lo <= pos <= band_hi:
                n += 1
        return n

    # Counts typed over in the builder's ranking summary win: "now" is the
    # newest month, "prev" the month before it (never the Initial column).
    typed = ((overrides or {}).get("bands") or {})
    rows = []
    for text_key, lo, hi in POSITION_BANDS:
        counts = [count(lo, hi, c) for c in columns]
        cell = typed.get(text_key.split(".", 1)[1]) or {}
        if cell.get("now") is not None and months:
            counts[0] = int(cell["now"])
        if cell.get("prev") is not None and len(months) > 1:
            counts[1] = int(cell["prev"])
        if cell.get("initial") is not None:
            counts[-1] = int(cell["initial"])
        rows.append({"name": t(text_key), "counts": counts})

    printed = [initial_label if c == INITIAL else c for c in columns]

    return {
        "columns": printed,
        "rows": rows,
        # The chart runs the other way: start on the left, now on the right.
        "chart_columns": [initial_label] + list(months),
        "chart_rows": [{"name": r["name"], "counts": list(reversed(r["counts"]))} for r in rows],
        "on_page_one": rows[0]["counts"][0] if rows and rows[0]["counts"] else 0,
    }


def ranking_highlights(keywords: list[dict], journey: list[dict], bands: list[dict]) -> list[dict]:
    """The two or three facts worth pulling out of the ranking tables."""
    out: list[dict] = []

    if len(journey) >= 2:
        gained = round(journey[0]["avg"] - journey[-1]["avg"], 1)
        if gained > 0:
            out.append({
                "value": f"{gained:g} places",
                "name": f"gained on average position since {journey[0]['label']}",
            })

    if len(bands) >= 2:
        more = bands[-1]["top10"] - bands[0]["top10"]
        if more > 0:
            out.append({
                "value": f"+{more}",
                "name": f"more keywords on page 1 than {bands[0]['label']}",
            })

    months = [j["label"] for j in journey]
    pairs = [(p, k) for k, p in zip(keywords, latest_positions(keywords, months)) if p > 0]
    best = min(pairs, key=lambda r: r[0], default=None)
    if best and best[0] <= 3:
        out.append({
            "value": f"#{int(best[0])}",
            "name": f"for “{best[1].get('term', '')}”",
        })

    return out[:3]


# ── Business Profile ────────────────────────────────────────────────────────

def gbp_figures(gbp: dict, deltas: dict, t=None) -> dict:
    """Interactions, the actions behind them, and how the profile was found."""
    from app.services.report_text import resolver
    t = t or resolver(None)

    actions = []
    total = 0.0
    total_change = 0.0
    for key, text_key in GBP_ACTIONS:
        value = _n(gbp.get(key))
        total += value
        total_change += _n(deltas.get(key))
        actions.append({
            "name": t(text_key),
            "value": _fmt(value),
            "raw": value,
            "change": _n(deltas.get(key)),
        })

    discovery = [
        {"name": t(text_key), "value": _n(gbp.get(key))}
        for key, text_key in GBP_DISCOVERY
    ]
    discovery.sort(key=lambda d: d["value"], reverse=True)

    return {
        "gbp_interactions": total,
        "gbp_interactions_change": total_change,
        "gbp_actions": actions[:5],
        "gbp_discovery": discovery,
        "gbp_views": sum(d["value"] for d in discovery),
    }


# ── The figures that lead the deck ──────────────────────────────────────────

def _previous_leads_of(data: dict) -> dict:
    from app.services.report_composer import previous_leads
    return previous_leads(data)


def lead_figures(ga4: dict, deltas: dict, t=None, previous: Optional[dict] = None) -> dict:
    """The individual lead actions, plus whatever the property calls its own.

    Revenue sits beside them because a transaction without its value answers
    only half the question.
    """
    from app.services.report_text import resolver
    t = t or resolver(None)

    events = ga4.get("events") or {}
    # Figures typed in the builder replace what the event names give.
    overrides = ga4.get("lead_overrides") or {}
    claimed: set[str] = set()
    figures: list[dict] = []

    for text_key, needles in LEAD_FIGURES:
        total = 0.0
        for event, count in events.items():
            low = event.lower()
            if any(n in low for n in needles):
                total += _n(count)
                claimed.add(event)
        key = text_key.split(".", 1)[1]
        if key in overrides:
            total = _n(overrides[key])
        # Every figure prints, 0 included — only the builder's Show switch hides one.
        figure = {"name": t(text_key), "value": _fmt(total), "raw": total}
        # Beside last period's figure when it is known.
        if (previous or {}).get(key) is not None:
            figure["change"] = total - _n(previous[key])
        figures.append(figure)

    revenue = _n(ga4.get("revenue"))
    figures.append({"name": t("lead.revenue"), "value": _fmt(revenue), "raw": revenue,
                    "change": _n(deltas.get("revenue"))})

    # Events the patterns above did not recognise. Shown under their own names
    # rather than dropped, so a property with house naming is not silently
    # reported as having produced no leads.
    other = sorted(
        ((e, _n(c)) for e, c in events.items()
         if e not in claimed and e.lower() not in GA4_AUTOMATIC_EVENTS and _n(c)),
        key=lambda ec: -ec[1],
    )

    from_events = sum(f["raw"] for f in figures if f["name"] != t("lead.revenue"))
    total_leads = from_events or _n(ga4.get("conversions"))
    # A total typed in the builder wins over the sum of the figures.
    if _n(overrides.get("total")):
        total_leads = _n(overrides.get("total"))

    return {
        "lead_figures": figures,
        "lead_events": [{"name": e, "value": _fmt(c)} for e, c in other],
        "leads_total": total_leads,
        # Only when the total and the stored change are the same measurement.
        # The delta is recorded against GA4's single `conversions` figure, so
        # against a total summed from named events it is arithmetic between two
        # different things.
        "leads_change": (total_leads - _n((previous or {}).get("total")))
        if (previous or {}).get("total") is not None
        else (0.0 if from_events else _n(deltas.get("conversions"))),
        "leads_from_events": bool(from_events),
    }


def _duration(seconds: float) -> str:
    """Seconds as GA4 prints them: "13s", "1m 05s"."""
    seconds = int(round(seconds))
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def _per(num: str, den: str):
    """A ratio of two stored figures, 0 where there is nothing to divide by."""
    return lambda c: _n(c.get(num)) / _n(c.get(den)) if _n(c.get(den)) else 0.0


# The columns of GA4's own comparison reports, each worked out from the
# additive figures stored per row: (heading, how to work it out, how to print).
_CHANNEL_COLUMNS: list[tuple[str, Any, Any]] = [
    ("Sessions", lambda c: _n(c.get("sessions")), _fmt),
    ("Engaged sessions", lambda c: _n(c.get("engaged_sessions")), _fmt),
    ("Engagement rate", lambda c: _per("engaged_sessions", "sessions")(c) * 100, lambda v: f"{v:.1f}%"),
    ("Avg. engagement time", _per("engagement_seconds", "sessions"), _duration),
    ("Events per session", _per("event_count", "sessions"), lambda v: f"{v:.2f}"),
    ("Event count", lambda c: _n(c.get("event_count")), _fmt),
    ("Key events", lambda c: _n(c.get("key_events")), _fmt),
]

# GA4's Demographic details report, by country. Revenue is added only when the
# site earns any, so a lead-generation site is not shown a column of zeros.
_COUNTRY_COLUMNS: list[tuple[str, Any, Any]] = [
    ("Active users", lambda c: _n(c.get("active_users")), _fmt),
    ("New users", lambda c: _n(c.get("new_users")), _fmt),
    ("Engaged sessions", lambda c: _n(c.get("engaged_sessions")), _fmt),
    ("Engagement rate", lambda c: _per("engaged_sessions", "sessions")(c) * 100, lambda v: f"{v:.1f}%"),
    ("Engaged sessions per user", _per("engaged_sessions", "active_users"), lambda v: f"{v:.2f}"),
    ("Avg. engagement time", _per("engagement_seconds", "active_users"), _duration),
    ("Event count", lambda c: _n(c.get("event_count")), _fmt),
    ("Key events", lambda c: _n(c.get("key_events")), _fmt),
]
_REVENUE_COLUMN = ("Revenue", lambda c: _n(c.get("revenue")), _fmt)


def comparison_table(current: Any, previous: Any, name_key: str,
                     columns: list[tuple[str, Any, Any]], limit: int = 4, show_prev: bool = True) -> dict:
    """A GA4 comparison view: the biggest rows, each figure beside the same
    row's figure last period and the change between them, plus a total."""
    current = [c for c in (current or []) if isinstance(c, dict)]
    if not current:
        return {"columns": [], "rows": [], "has_previous": False}
    before = {c.get(name_key): c for c in (previous or []) if isinstance(c, dict)}
    has_previous = bool(before)

    def total(rows) -> dict:
        out: dict[str, float] = {}
        for r in rows:
            for k, v in r.items():
                if k != name_key:
                    out[k] = out.get(k, 0.0) + _n(v)
        return out

    def cells(now: dict, was_row: Optional[dict]) -> list[dict]:
        out = []
        for _, calc, show in columns:
            value = calc(now)
            cell: dict[str, Any] = {"value": show(value), "prev": None, "change": None}
            if has_previous:
                was = calc(was_row or {})
                # Over several months the baseline is worked out, not a real
                # earlier figure, so only the change prints.
                cell["prev"] = show(was) if show_prev else None
                # A row with nothing last period has no percentage to grow
                # by; the previous figure (0) says so on its own.
                cell["change"] = round((value - was) / was * 100, 1) if was else None
            out.append(cell)
        return out

    return {
        "columns": [name for name, _, _ in columns],
        "rows": [{"name": c.get(name_key), "cells": cells(c, before.get(c.get(name_key)))}
                 for c in current[:limit]],
        "total": {"name": "Total", "cells": cells(total(current), total(before.values()))},
        "has_previous": has_previous,
    }


def channel_table(ga4: dict) -> dict:
    """GA4's Traffic acquisition view, by default channel group."""
    ga4 = ga4 or {}
    return comparison_table(ga4.get("channels"), ga4.get("channels_previous"), "channel", _CHANNEL_COLUMNS,
                            show_prev=not ga4.get("_span_compare"))


def country_table(ga4: dict) -> dict:
    """GA4's Demographic details view, by country."""
    ga4 = ga4 or {}
    rows = ga4.get("countries_detail") or []
    columns = list(_COUNTRY_COLUMNS)
    if any(_n(r.get("revenue")) for r in rows if isinstance(r, dict)):
        columns.append(_REVENUE_COLUMN)
    return comparison_table(rows, ga4.get("countries_detail_previous"), "country", columns,
                            show_prev=not ga4.get("_span_compare"))


def _nice_ceiling(value: float) -> float:
    """A round axis top at or above `value`: 12, 3,800 → 4,000 and so on."""
    if value <= 0:
        return 1.0
    import math
    step = 10 ** math.floor(math.log10(value))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= m * step:
            return m * step
    return 10 * step


def _thirds_ceiling(value: float) -> float:
    """An axis top split into three round steps (0, 4, 8, 12), as Search
    Console draws its axes."""
    if value <= 3:
        return 3.0
    import math
    third = value / 3
    scale = 10 ** math.floor(math.log10(third))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if third <= m * scale:
            return 3 * m * scale
    return 30 * scale


def _axis_label(value: float) -> str:
    if value >= 1000:
        text = f"{value / 1000:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return f"{value:.0f}" if value >= 10 or value == int(value) else f"{value:.1f}"


def gsc_console(gsc: dict, width: int = 1100, height: Optional[int] = None) -> dict:
    """Search Console's Performance view: the four totals, the daily clicks
    and impressions lines on their own axes, and the top queries."""
    gsc = gsc or {}
    days = [d for d in (gsc.get("daily") or []) if isinstance(d, dict) and d.get("date")]
    out: dict[str, Any] = {
        "clicks": _fmt(gsc.get("clicks")),
        "impressions": _compact(gsc.get("impressions")),
        "ctr": f"{_n(gsc.get('ctr')) * 100:.1f}%",
        "position": f"{_n(gsc.get('position')):.0f}" if _n(gsc.get("position")) >= 10 else f"{_n(gsc.get('position')):.1f}",
        "queries": [q for q in (gsc.get("top_queries") or []) if isinstance(q, dict)][:10],
        "chart": None,
    }
    if len(days) < 2:
        return out
    # The chart takes the room the queries table leaves: drawn at the size it
    # prints, so its labels are never stretched to fill a space.
    if height is None:
        # Ten queries under the chart need the room; without them the chart takes it.
        height = 118 if len(out["queries"]) > 7 else (170 if out["queries"] else 330)

    top_c = _thirds_ceiling(max(_n(d.get("clicks")) for d in days))
    top_i = _thirds_ceiling(max(_n(d.get("impressions")) for d in days))
    step = width / (len(days) - 1)

    def line(key: str, top: float) -> str:
        return " ".join(
            f"{i * step:.1f},{height - _n(d.get(key)) / top * height:.1f}" for i, d in enumerate(days)
        )

    every = max(1, round(len(days) / 14))
    out["chart"] = {
        "width": width,
        "height": height,
        "clicks": line("clicks", top_c),
        "impressions": line("impressions", top_i),
        # Three steps up each side, as Search Console draws them.
        "ticks": [
            {"y": round(height - f * height, 1), "left": _axis_label(top_c * f), "right": _axis_label(top_i * f)}
            for f in (0, 1 / 3, 2 / 3, 1)
        ],
        "dates": [
            {"x": round(i * step, 1),
             "label": datetime.date.fromisoformat(d["date"]).strftime("%d/%m/%Y")}
            for i, d in enumerate(days) if i % every == 0
        ],
    }
    return out


def _compact(value: Any) -> str:
    """54,321 → "54.3k", the way Search Console prints its totals."""
    n = _n(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return _fmt(n)


# The assistants on the AI results slide, as the agency's own tools list them.
AI_SUMMARY_ENGINES = [
    ("chatgpt", "ChatGPT"),
    ("google_ai_overview", "AI Overview"),
    ("ai_mode", "AI Mode"),
    ("gemini", "Gemini"),
]


def ai_summary(data: dict) -> dict:
    """AI Visibility score, total mentions, total cited pages, and each
    assistant's mentions and cited pages. Worked out from the prompt checks
    where they say it; any figure typed in the builder wins."""
    rows = [r for r in (data.get("ai_visibility") or []) if isinstance(r, dict)]
    # The usual assistants, plus every other one the prompt checks cover —
    # a Perplexity or Claude answer counts toward the totals like any other.
    engine_list = list(AI_SUMMARY_ENGINES)
    for r in rows:
        key = str(r.get("platform") or "")
        if key and key not in {k for k, _ in engine_list}:
            engine_list.append((key, ENGINE_NAME.get(key, key.replace("_", " ").title())))
    # …and every assistant a figure was typed or read in for.
    typed_keys = ((data.get("ai_summary") or {}).get("engines") or {}) if isinstance(data.get("ai_summary"), dict) else {}
    for key in typed_keys:
        if key not in {k for k, _ in engine_list}:
            engine_list.append((key, ENGINE_NAME.get(key, key.replace("_", " ").title())))
    auto_engines: dict[str, dict] = {k: {"mentions": 0, "cited": 0} for k, _ in engine_list}
    for r in rows:
        key = str(r.get("platform") or "")
        if key not in auto_engines:
            continue
        if r.get("mentioned"):
            auto_engines[key]["mentions"] += 1
        cited = r.get("cited_pages")
        if isinstance(cited, list):
            auto_engines[key]["cited"] += len(cited)
    hit = sum(1 for r in rows if r.get("mentioned"))
    auto = {
        "score": round(hit / len(rows) * 100) if rows else 0,
        "engines": auto_engines,
    }

    typed = data.get("ai_summary") if isinstance(data.get("ai_summary"), dict) else {}
    typed_engines = typed.get("engines") if isinstance(typed.get("engines"), dict) else {}
    engines = []
    for key, name in engine_list:
        own = typed_engines.get(key) if isinstance(typed_engines.get(key), dict) else {}
        engines.append({
            "key": key, "name": name,
            "mentions": int(own["mentions"]) if own.get("mentions") is not None else auto_engines[key]["mentions"],
            "cited": int(own["cited"]) if own.get("cited") is not None else auto_engines[key]["cited"],
        })
    auto["mentions"] = sum(e["mentions"] for e in auto_engines.values())
    auto["cited"] = sum(e["cited"] for e in auto_engines.values())
    score = typed.get("score") if typed.get("score") is not None else auto["score"]
    return {
        "score": max(0, min(100, int(score))),
        "mentions": int(typed["mentions"]) if typed.get("mentions") is not None else sum(e["mentions"] for e in engines),
        "cited": int(typed["cited"]) if typed.get("cited") is not None else sum(e["cited"] for e in engines),
        "engines": engines,
        "typed": bool(typed),
        "auto": auto,
    }


def ai_visibility_rate(data: dict) -> dict:
    """How often the assistants name the brand, as a share of the checks run.

    A share, not "62 of 108": the number of tracked prompts is a decision the
    agency makes, so a raw count moves whenever that decision does and reads
    like a score out of a total the client never agreed to.
    """
    rows = [r for r in (data.get("ai_visibility") or []) if isinstance(r, dict)]
    if not rows:
        return {"rate": 0.0, "value": "", "change": 0.0, "has_change": False}

    hit = sum(1 for r in rows if r.get("mentioned"))
    rate = hit / len(rows) * 100
    compare = data.get("ai_compare") if isinstance(data.get("ai_compare"), dict) else {}
    before = _n(compare.get("previous_rate"))
    has_change = bool(compare.get("hasData"))

    return {
        "rate": rate,
        "value": f"{rate:.0f}%",
        # A rate's movement is in percentage points, so the change is the
        # difference between the two rates, not a percentage of a percentage.
        "change": round(rate - before, 1) if has_change else 0.0,
        "has_change": has_change,
        "mentioned": hit,
        "checks": len(rows),
        # The AI slide shows counts ("34 of 60"), so it moves by answers gained
        # or lost rather than by points of share.
        "mentioned_change": (hit - int(_n(compare.get("previous_mentioned"))))
        if has_change and "previous_mentioned" in compare else 0,
    }


def page_one(data: dict) -> tuple[int, int, Optional[int]]:
    """Keywords in the top 10 now, keywords in all, and the top 10 last
    period (None when unknown) — from the ranking summary's bands, so typed
    counts and worked-out ones agree everywhere they print."""
    from app.services.report_composer import rank_bands_final
    rankings = data.get("rankings") or {}
    keywords = rankings.get("keywords") or []
    # The comparative rows keep positions by month; the band counter reads
    # the flat fields, so give it the newest position under "position".
    months = data.get("months") or []
    flat = [{**k, "position": p} for k, p in zip(keywords, latest_positions(keywords, months))]
    bands = rank_bands_final(flat, rankings.get("summary_overrides"))
    top = bands["top10"]
    return int(top["now"] or 0), int(sum(b["now"] or 0 for b in bands.values())), top["prev"]


def scorecard(data: dict, sections: dict, metric_on, baseline: bool = False, t=None) -> list[dict]:
    """The eight figures the report leads with, in the order it names them.

    The order is fixed rather than sorted by size: a reader comparing two
    months should find the same figure in the same place both times.
    """
    gsc = data.get("gsc") or {}
    ga4 = data.get("ga4") or {}
    gbp = data.get("gbp") or {}
    deltas = data.get("kpi_deltas") or {}

    from app.services.report_text import resolver
    t = t or resolver(None)

    cards: list[dict] = []

    def add(card: str, name: str, value: str, raw: float, change: float = 0.0,
            note: str = "", tag: str | None = None, highlight: bool = False) -> None:
        cards.append({
            "card": card, "name": name, "value": value, "raw": raw, "change": change,
            "note": note, "highlight": highlight,
            # Without a comparison the card would otherwise sit bare, reading
            # as a figure whose change failed to load rather than one that has
            # nothing to be compared against yet.
            "tag": tag or (t("tag.baseline") if baseline else None),
        })

    # 1 · Keyword rankings
    if sections.get("rankings"):
        # The same counts as the ranking summary, so a figure typed there
        # (top 10 this month, last month, keywords in all) shows here too.
        top10, tracked, top10_before = page_one(data)
        change = (top10 - top10_before) if top10_before is not None else 0.0
        add("keywords", t("kpi.keywords.name"), f"{top10}", top10, change,
            note=t("kpi.keywords.note"), highlight=True,
            tag=t("tag.baseline") if baseline else (None if top10_before else t("tag.tracked")))

    # 2–3 · Search Console
    if sections.get("gsc"):
        if metric_on("gsc.clicks"):
            add("clicks", t("kpi.clicks.name"), _fmt(gsc.get("clicks")), _n(gsc.get("clicks")),
                _n((deltas.get("gsc") or {}).get("clicks")))
        if metric_on("gsc.impressions"):
            add("impressions", t("kpi.impressions.name"), _fmt(gsc.get("impressions")), _n(gsc.get("impressions")),
                _n((deltas.get("gsc") or {}).get("impressions")))

    # 4 · Website traffic
    if sections.get("ga4") and metric_on("ga4.sessions"):
        add("sessions", t("kpi.sessions.name"), _fmt(ga4.get("sessions")), _n(ga4.get("sessions")),
            _n((deltas.get("ga4") or {}).get("sessions")))

    # 5–6 · Leads and revenue
    from app.services.report_composer import previous_leads
    leads = lead_figures(ga4, (deltas.get("ga4") or {}), t, previous_leads(data))
    if sections.get("ga4") and metric_on("ga4.conversions"):
        add("leads", t("kpi.leads.name"), _fmt(leads["leads_total"]), leads["leads_total"], leads["leads_change"],
            note=t("kpi.leads.note") if leads["leads_from_events"] else "",
            tag=t("tag.baseline") if baseline else (None if leads["leads_change"] else t("tag.this_period")))
    if sections.get("ga4") and metric_on("ga4.revenue"):
        add("revenue", t("kpi.revenue.name"), _fmt(ga4.get("revenue")), _n(ga4.get("revenue")),
            _n((deltas.get("ga4") or {}).get("revenue")))

    # 7 · AI visibility
    if sections.get("ai_visibility"):
        ai = ai_visibility_rate(data)
        # Shown as a count of answers, to match the AI results slide —
        # its Total Mentions when one was typed there.
        typed = (data.get("ai_summary") or {}).get("mentions")
        count = int(typed) if typed is not None else int(ai.get("mentioned", 0))
        add("ai", t("kpi.ai.name"), _fmt(count), count, ai.get("mentioned_change", 0.0) if typed is None else 0.0,
            note=t("kpi.ai.note"), highlight=True,
            tag=None if ai.get("has_change") else (t("tag.baseline") if baseline else t("tag.ai")))

    # 8 · Traffic arriving from the assistants themselves
    referral = ai_referral_traffic(ga4)
    if sections.get("ga4"):
        add("ai_traffic", t("kpi.ai_traffic.name"), _fmt(referral["sessions"]), _n(referral["sessions"]),
            note=t("kpi.ai_traffic.note"), tag=t("tag.ai"))

    # A Business Profile is not one of the eight, but a local client whose
    # profile is the whole story would otherwise lead with nothing from it.
    gbp_total = sum(_n(gbp.get(k)) for k, _ in GBP_ACTIONS)
    hidden = set(data.get("hidden_cards") or [])
    if sections.get("gbp"):
        add("gbp", t("kpi.gbp.name"), _fmt(gbp_total), gbp_total,
            sum(_n((deltas.get("gbp") or {}).get(k)) for k, _ in GBP_ACTIONS))

    # Cards switched off in the builder are left out.
    return [c for c in cards if c["card"] not in hidden]


def headline_stats(cards: list[dict], baseline: bool = False) -> list[dict]:
    """The three figures the executive summary leads with.

    A progress report opens on what moved most. A first report has nothing to
    rank by movement, so it opens on the figures that are actually standing
    up — anything still at zero is the work not yet done, not the result.
    """
    if baseline:
        ranked = [c for c in cards if not _leads_with_zero(c["value"])]
    else:
        ranked = sorted(
            cards,
            key=lambda c: abs(_pct_change(c.get("raw"), c.get("change")) or 0),
            reverse=True,
        )

    out = []
    for c in ranked[:3]:
        pct = None if baseline else _pct_change(c.get("raw"), c.get("change"))
        out.append({
            "value": c["value"],
            "name": c["name"],
            "note": (f"{'+' if pct > 0 else ''}{pct}% against the period before"
                     if pct else c.get("note") or ""),
        })
    return out


def _leads_with_zero(value: Any) -> bool:
    """Whether a figure amounts to nothing yet — "0", "0 / 8", "0%"."""
    head = str(value).strip().split("/")[0].strip().rstrip("%")
    try:
        return float(head.replace(",", "")) == 0
    except ValueError:
        return False


# ── The plan ────────────────────────────────────────────────────────────────

def plan_lanes(next_month_plan: Any) -> tuple[list[dict], list[dict]]:
    """The two roadmap lanes, as staff entered them."""
    plan = next_month_plan if isinstance(next_month_plan, dict) else {}

    def lane(key: str) -> list[dict]:
        rows = plan.get(key)
        if not isinstance(rows, list):
            return []
        out = []
        for row in rows:
            if isinstance(row, dict) and str(row.get("title") or "").strip():
                out.append({
                    "title": str(row["title"]).strip(),
                    "detail": str(row.get("detail") or "").strip(),
                })
            elif isinstance(row, str) and row.strip():
                out.append({"title": row.strip(), "detail": ""})
        return out[:3]

    return lane("now"), lane("next")


# Referrers that are AI assistants rather than search engines or sites. GA4
# reports them like any other referral, so recognising them is what turns a
# row in the traffic table into "someone arrived from ChatGPT".
AI_REFERRERS = {
    "chatgpt.com": "ChatGPT",
    "chat.openai.com": "ChatGPT",
    "openai.com": "ChatGPT",
    "perplexity.ai": "Perplexity",
    "www.perplexity.ai": "Perplexity",
    "gemini.google.com": "Gemini",
    "bard.google.com": "Gemini",
    "copilot.microsoft.com": "Copilot",
    "www.bing.com/chat": "Copilot",
    "claude.ai": "Claude",
    "you.com": "You.com",
    "poe.com": "Poe",
}


def ai_referral_traffic(ga4: dict) -> dict:
    """Visits that arrived from an AI assistant rather than a search result.

    This is the one AI figure that is not a prompt check: it is real people
    who asked an assistant something and clicked through. GA4 already reports
    the referrer, so it only needs recognising.
    """
    rows = (ga4 or {}).get("traffic_sources") or []
    # The share is of every visit this period; the source list is only the top ten.
    total_sessions = _n((ga4 or {}).get("sessions")) or sum(_n(r.get("sessions")) for r in rows) or 0.0

    found: dict[str, float] = {}
    for r in rows:
        name = AI_REFERRERS.get(str(r.get("source") or "").strip().lower())
        if name:
            found[name] = found.get(name, 0.0) + _n(r.get("sessions"))

    # Visits typed in the builder replace what GA4 reported. Every assistant
    # is listed, 0 included — only the builder's Show switch hides one.
    for name, value in ((ga4 or {}).get("ai_referral_overrides") or {}).items():
        found[name] = _n(value)
    for name in AI_REFERRAL_ENGINES:
        found.setdefault(name, 0.0)

    sessions = sum(found.values())
    return {
        "sessions": sessions,
        "share": round(sessions / total_sessions * 100, 1) if total_sessions else 0.0,
        "engines": sorted(
            ({"name": n, "sessions": v} for n, v in found.items()),
            key=lambda e: e["sessions"], reverse=True,
        ),
    }


# The assistants the builder offers a figure for, in the order it lists them.
AI_REFERRAL_ENGINES = ["ChatGPT", "Perplexity", "Gemini", "Claude", "Copilot"]


# Assistants have names, not slugs. Title-casing "chatgpt" gives "Chatgpt".
ENGINE_NAME = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
    "perplexity": "Perplexity",
    "grok": "Grok",
    "google_ai_overview": "AI Overview",
    "ai_mode": "AI Mode",
    "copilot": "Copilot",
}


def ai_visibility_matrix(rows: Any) -> dict:
    """Each tracked prompt against each assistant — visible or not.

    A count of mentions says how many; this says which, which is the question
    a client actually asks. One row per prompt, one column per engine.
    """
    grid: dict[str, dict[str, bool]] = {}
    engines: list[str] = []
    for m in (rows or []):
        if not isinstance(m, dict):
            continue
        prompt = str(m.get("prompt") or m.get("prompt_text") or "").strip()
        slug = str(m.get("platform") or "").strip().lower()
        engine = ENGINE_NAME.get(slug, slug.replace("_", " ").title())
        if not prompt or not engine:
            continue
        if engine not in engines:
            engines.append(engine)
        grid.setdefault(prompt, {})[engine] = bool(m.get("mentioned"))

    ordered = sorted(
        grid.items(),
        key=lambda kv: sum(1 for v in kv[1].values() if v),
        reverse=True,
    )

    return {
        "engines": engines,
        "rows": [{"prompt": p, "seen": [cells.get(e) for e in engines]} for p, cells in ordered],
        "total_prompts": len(grid),
    }


# What a reader is told about where a section's figures came from. §15 makes
# this load-bearing: the report must never let a hand-typed figure pass for
# one Google reported.
SOURCE_NAME = {
    "gsc": "Google Search Console",
    "ga4": "Google Analytics 4",
    "gbp": "Google Business Profile",
    "rankings": "daily rank tracking",
    "ai_visibility": "AI assistant checks",
}

# Sections nothing automated ever writes to, so naming a provider would be a
# lie — they are only ever a record of what the agency did.
AGENCY_KEPT = {"links", "work"}


def source_lines(provenance: Any) -> dict[str, str]:
    """One caption per section, naming where its figures came from."""
    rows = provenance if isinstance(provenance, dict) else {}
    out: dict[str, str] = {}

    for section in AGENCY_KEPT:
        if (rows.get(section) or {}).get("source"):
            out[section] = "Source: recorded by the agency."

    for section, name in SOURCE_NAME.items():
        source = (rows.get(section) or {}).get("source")
        if source == "api":
            out[section] = f"Source: {name}, collected automatically."
        elif source == "manual":
            out[section] = f"Source: {name}, entered by hand."
        elif source == "mixed":
            out[section] = f"Source: {name}, partly collected automatically, partly entered by hand."
    return out


def brief(text: Any, sentences: int = 2, cap: int = 240) -> str:
    """The opening of a long narrative, for the one line a slide can hold.

    A slide is a fixed page: the full narrative belongs in the commentary
    panel, not spilling past the footer. This takes its first sentences and
    stops on a sentence boundary rather than mid-word.
    """
    body = " ".join(str(text or "").split())
    if not body:
        return ""
    out, count = "", 0
    for chunk in body.replace("! ", ". ").replace("? ", ". ").split(". "):
        candidate = f"{out}. {chunk}".strip(". ") if out else chunk
        if len(candidate) > cap and out:
            break
        out, count = candidate, count + 1
        if count >= sentences:
            break
    out = out.strip()
    if out and not out.endswith((".", "!", "?")):
        out += "."
    return out


def build(data: dict, client: dict, sections: dict, metric_on,
          display_label: str, period_range: str = "", t=None) -> dict:
    """Every derived value the slide template asks for.

    `t` resolves a fixed string by id, so the agency's wording reaches the
    figures built here and not only the ones printed in the template.
    """
    from app.services.report_text import resolver
    t = t or resolver(None)
    keywords = (data.get("rankings") or {}).get("keywords") or []
    months = data.get("months") or []

    from app.services.report_period import has_comparison
    compare = (data.get("period") or {}).get("compare") or {}
    compared = has_comparison(data)
    compare_label = (compare.get("range") or "") if compared else ""

    # With nothing stored for an earlier period there is nothing to compare
    # against, which is not a gap in the report — it is the whole character of
    # a first one. Said plainly, it turns an absence into information.
    # A report spanning several months carries its own earlier months, so it is
    # never a client's "first report" even with nothing before it.
    baseline = not compared

    journey = ranking_journey(keywords, months)
    bands = ranking_bands(keywords, months)
    established = starting_positions(keywords, months) if baseline else None
    cards = scorecard(data, sections, metric_on, baseline, t)
    plan = data.get("next_month_plan") if isinstance(data.get("next_month_plan"), dict) else {}
    now_items, next_items = plan_lanes(plan)

    name = client.get("name") or "this client"
    top10, tracked_total, _ = page_one(data)

    closing = f"Let’s keep {name} moving up the search results."
    note = ""
    typed_note = str(((data.get("copy") or {}).get("texts") or {}).get("closing.note") or "").strip()
    if typed_note:
        # A sign-off typed in the builder is the agency's own; it wins.
        note = t("closing.note")
    elif keywords and top10:
        note = (f"{top10} of {tracked_total} tracked keywords now sit on page one. "
                f"Share any feedback and we’ll set next month’s targets together.")
    else:
        note = t("closing.note")

    # Biggest first, and only as many as the card can hold beside a
    # commentary panel — a longer list would be clipped rather than read.
    link_kinds = sorted(
        (data.get("link_types") or {}).items(),
        key=lambda kv: _n(kv[1]),
        reverse=True,
    )

    ga4 = data.get("ga4") or {}
    ai_referral = ai_referral_traffic(ga4)

    # Proof captures, six to a page — three across, two down. Matching on the
    # caption to pick out the AI ones was wrong: "Claude" and "Perplexity" do
    # not contain the word, so five of six captures silently vanished.
    # Captures uploaded in the builder's AI Visibility step win; without any,
    # the client's saved screenshots for the month are used as before.
    shots = [s for s in (data.get("ai_shots") or []) if isinstance(s, dict)] \
        or [s for s in (data.get("screenshots") or []) if isinstance(s, dict)]
    ai_proof_pages = [shots[i:i + 6] for i in range(0, len(shots), 6)]

    return {
        "ai_proof_pages": ai_proof_pages,
        # Last month's column too, when a one-month report knows it.
        "position_bands": position_bands(keywords, data.get("rank_months") or months, t,
                                         (data.get("rankings") or {}).get("summary_overrides")),
        "ai_referral": ai_referral,
        "ai_matrix": ai_visibility_matrix(data.get("ai_visibility")),
        "ai_rate": ai_visibility_rate(data),
        "ai_summary": ai_summary(data),
        "gsc_console": gsc_console(data.get("gsc") or {}),
        "ga4_channels": channel_table(ga4),
        "ga4_country_table": country_table(ga4),
        "source_lines": source_lines(data.get("provenance")),
        "link_kinds": link_kinds,
        "summary_lede": brief(data.get("narrative")),
        "cover_lede": (data.get("cover_lede")
                       or f"Search visibility, keyword rankings and customer engagement for "
                          f"{client.get('domain') or name}."),
        "period_range": period_range,
        "generated_month": datetime.date.today().strftime("%B %Y"),

        "headline_stats": headline_stats(cards, baseline),
        "scorecard": cards,
        "compare_label": compare_label,
        # A several-month report's label already reads "September vs Jun–Aug average".
        "compare_vs": "" if compare.get("span") else "vs ",
        "baseline": baseline,
        "baseline_note": (
            "This is the first report for this client, so there is no earlier period to "
            "measure against yet. The figures below are the starting point every following "
            "month is compared with."
        ) if baseline else "",

        "rank_journey": journey,
        "rank_bands": bands,
        "starting_positions": established,
        "rank_highlights": ranking_highlights(keywords, journey, bands),

        **gbp_figures(data.get("gbp") or {}, (data.get("kpi_deltas") or {}).get("gbp") or {}, t),
        **lead_figures(ga4, (data.get("kpi_deltas") or {}).get("ga4") or {}, t, _previous_leads_of(data)),

        "plan_now": now_items,
        "plan_next": next_items,
        "plan_lede": plan.get("lede") or data.get("plan_lede") or "",

        "closing_line": closing,
        "closing_note": note,
    }
