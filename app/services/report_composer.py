"""Enumerates every tickable, editable piece of a report snapshot.

One place defines what the composer shows, what the AI may switch, and what the
report and PDF are allowed to render — so the four can never drift apart.

Every datum has a stable id of the form ``<section>.<...>``. Ids for list rows
are built from the row's own identifier where one exists, so a selection
survives re-reads of the same snapshot.
"""
from __future__ import annotations

from typing import Any

# Order here is the order the composer and the report present things in.
SECTIONS: list[dict[str, str]] = [
    {"key": "gsc", "label": "Search Console"},
    {"key": "ga4", "label": "Google Analytics"},
    {"key": "gbp", "label": "Business Profile"},
    {"key": "rankings", "label": "Rankings"},
    {"key": "ai_visibility", "label": "AI Visibility"},
    {"key": "links", "label": "Links Built"},
    {"key": "work", "label": "Work Done"},
]

SECTION_KEYS = [s["key"] for s in SECTIONS]

# Where a block's commentary came from. Kept beside the text itself so a
# regenerated report can refresh its own drafts without ever overwriting a
# sentence a person wrote — and so the builder can say which is which.
NARRATION_AI = "ai"
NARRATION_EDITED = "edited"

# Commentary is keyed to the report's titled BLOCKS, not to its data sections:
# "Device Breakdown (GA4)" and "Top Traffic Sources (GA4)" are both part of the
# analytics section but each gets its own heading in the report, so each gets
# its own paragraph. NARRATION_BLOCKS is derived from COPY_HEADINGS further
# down this file, so a block can never exist with a title but no commentary.
#
# Headings that print but carry no commentary of their own: the executive
# summary already holds the report-level narrative, the ranking table is the
# evidence behind a slide that is already written about, and the last four
# are chrome rather than findings.
NARRATION_EXCLUDED = {
    "exec_summary", "rankings_table", "gbp_discovery", "ai_proof", "evidence", "plan", "closing",
    # The traffic-sources slide is no longer printed.
    "ga4_sources",
    # Screenshots only; there is nothing for commentary to describe.
    "gbp_proof",
    # A straight copy of Google's own view, with no room for commentary.
    "gsc_console",
    # Its commentary is the AI visibility block's, printed on this slide.
    "ai_results",
}

# Headline figures, per provider section.
HEADLINE: dict[str, list[dict[str, str]]] = {
    "gsc": [
        {"key": "clicks", "label": "Total clicks", "format": "int"},
        {"key": "impressions", "label": "Total impressions", "format": "int"},
        {"key": "ctr", "label": "Average CTR", "format": "percent"},
        {"key": "position", "label": "Average position", "format": "decimal"},
    ],
    "ga4": [
        {"key": "sessions", "label": "Sessions", "format": "int"},
        {"key": "users", "label": "Total users", "format": "int"},
        {"key": "engaged_sessions", "label": "Engaged sessions", "format": "int"},
        {"key": "conversions", "label": "Conversions", "format": "int"},
        {"key": "revenue", "label": "Revenue", "format": "decimal"},
    ],
    "gbp": [
        {"key": "calls", "label": "Calls", "format": "int"},
        {"key": "direction_requests", "label": "Direction requests", "format": "int"},
        {"key": "website_clicks", "label": "Website clicks", "format": "int"},
        {"key": "bookings", "label": "Bookings", "format": "int"},
    ],
}

# Every figure the report prints beside last period's, per section. Each gets
# a "Previous month | This month" pair in the builder, and its change is
# always this period minus the previous one.
def comparable_keys() -> dict[str, list[str]]:
    out = {s: [m["key"] for m in metas] for s, metas in HEADLINE.items()}
    out["gbp"] = out["gbp"] + [m["key"] for m in GBP_EXTRA]
    return out


RANKING_SUMMARY = [
    {"key": "top_10", "label": "Top 10"},
    {"key": "11_20", "label": "11–20"},
    {"key": "21_50", "label": "21–50"},
    {"key": "51_plus", "label": "51+"},
    {"key": "improved", "label": "Improved"},
    {"key": "declined", "label": "Declined"},
]


# Leads & Conversion figures. GA4 names events per site, so each is found by
# pattern (slide_deck.LEAD_FIGURES); a value typed in the builder replaces
# what was found, and 0 hides the figure.
LEAD_KEYS = [
    {"key": "thank_you", "label": "Thank-you page"},
    {"key": "email", "label": "Email clicks"},
    {"key": "phone", "label": "Phone number clicks"},
    {"key": "transactions", "label": "Transactions"},
]

# Business Profile figures that print but are not KPI cards: chat clicks on
# the performance slide, and the four impression splits on "How people found
# your profile".
GBP_EXTRA = [
    {"key": "chat_clicks", "label": "Chat clicks"},
]

# The tables behind the report's breakdown slides, each editable in the
# builder as rows: fix a cell, add a row, remove one. `columns` are
# (field, heading, type); the first is the row's name.
LIST_SPECS: list[dict] = [
    {"path": "gsc.trending_pages", "section": "gsc", "label": "Top performing pages",
     "note": "The Top Performing Pages slide: the pages trending up in Search Console, biggest gain first. The image is the picture shown beside each page — paste any image address to change it, or clear it.",
     "columns": [("page", "Page URL", "text"), ("clicks", "Clicks now", "int"),
                 ("prev_clicks", "Clicks last period", "int"), ("image", "Image URL", "text")]},
    {"path": "gsc.top_queries", "section": "gsc", "label": "Top queries",
     "note": "The Queries table on the Search Console Performance slide.",
     "columns": [("query", "Query", "text"), ("clicks", "Clicks", "int"), ("impressions", "Impressions", "int")]},
    {"path": "ga4.channels", "section": "ga4", "label": "Traffic by channel — this period",
     "note": "The channel table on Traffic Progress Summary. Rates and averages are worked out from these.",
     "columns": [("channel", "Channel", "text"), ("sessions", "Sessions", "int"),
                 ("engaged_sessions", "Engaged sessions", "int"),
                 ("engagement_seconds", "Engagement time (total seconds)", "int"),
                 ("event_count", "Event count", "int"), ("key_events", "Key events", "int")]},
    {"path": "ga4.channels_previous", "section": "ga4", "label": "Traffic by channel — previous period",
     "note": "What each channel is compared against.",
     "columns": [("channel", "Channel", "text"), ("sessions", "Sessions", "int"),
                 ("engaged_sessions", "Engaged sessions", "int"),
                 ("engagement_seconds", "Engagement time (total seconds)", "int"),
                 ("event_count", "Event count", "int"), ("key_events", "Key events", "int")]},
    {"path": "ga4.countries", "section": "ga4", "label": "Sessions by country",
     "note": "The share-of-visits donut on Geographical Distribution.",
     "columns": [("country", "Country", "text"), ("sessions", "Sessions", "int")]},
    {"path": "ga4.countries_detail", "section": "ga4", "label": "Users by country — this period",
     "note": "The country table on Geographical Distribution.",
     "columns": [("country", "Country", "text"), ("active_users", "Active users", "int"),
                 ("new_users", "New users", "int"), ("sessions", "Sessions", "int"),
                 ("engaged_sessions", "Engaged sessions", "int"),
                 ("engagement_seconds", "Engagement time (total seconds)", "int"),
                 ("event_count", "Event count", "int"), ("key_events", "Key events", "int"),
                 ("revenue", "Revenue", "decimal")]},
    {"path": "ga4.countries_detail_previous", "section": "ga4", "label": "Users by country — previous period",
     "note": "What each country is compared against.",
     "columns": [("country", "Country", "text"), ("active_users", "Active users", "int"),
                 ("new_users", "New users", "int"), ("sessions", "Sessions", "int"),
                 ("engaged_sessions", "Engaged sessions", "int"),
                 ("engagement_seconds", "Engagement time (total seconds)", "int"),
                 ("event_count", "Event count", "int"), ("key_events", "Key events", "int"),
                 ("revenue", "Revenue", "decimal")]},
    {"path": "links", "section": "links", "label": "Links built this month",
     "note": "One row per link: its kind (Guest Post, Profile…), how many, and where. Type them in or upload a sheet above.",
     "columns": [("activity_type", "Kind of link", "text"), ("count", "Count", "int"), ("url", "URL", "text")]},
    {"path": "activities", "section": "work", "label": "Work delivered this month",
     "note": "One row per task, with how many were done and a short note.",
     "columns": [("activity_type", "Task", "text"), ("count", "Count", "int"), ("notes", "Notes", "text")]},
    {"path": "ga4.traffic_sources", "section": "ga4", "label": "Traffic sources",
     "note": "AI Assistant Referral Traffic is built from these — add a row such as chatgpt.com to count visits from an assistant.",
     "columns": [("source", "Source", "text"), ("sessions", "Sessions", "int")]},
]
_LIST_BY_PATH = {spec["path"]: spec for spec in LIST_SPECS}


def list_rows(snapshot: dict, path: str) -> list[dict]:
    if "." not in path:
        rows = _s(snapshot).get(path) or []
    else:
        section, key = path.split(".", 1)
        rows = ((_s(snapshot).get(section) or {}).get(key)) or []
    return [r for r in rows if isinstance(r, dict)]


def write_list(snapshot: dict, path: str, rows: Any) -> bool:
    """Replace one breakdown table with edited rows. Declared columns are
    coerced to their type; other scalar fields on a row are kept as sent."""
    spec = _LIST_BY_PATH.get(path)
    if not spec or not isinstance(rows, list):
        return False
    name_key = spec["columns"][0][0]
    clean: list[dict] = []
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        out = {k: v for k, v in row.items() if isinstance(v, (int, float, str)) or v is None}
        name = str(row.get(name_key) or "").strip()
        if not name:
            continue
        out[name_key] = name[:300]
        for field, _, kind in spec["columns"][1:]:
            if kind == "text":
                text = str(row.get(field) or "").strip()[:1000]
                if text:
                    out[field] = text
                else:
                    out.pop(field, None)
                continue
            try:
                value = float(row.get(field) or 0)
            except (TypeError, ValueError):
                value = 0.0
            out[field] = max(0.0, round(value, 2) if kind == "decimal" else float(round(value)))
        clean.append(out)
    if path == "gsc.trending_pages":
        clean.sort(key=lambda r: (r.get("clicks", 0) - r.get("prev_clicks", 0), r.get("clicks", 0)), reverse=True)
    elif path in ("links", "activities"):
        # Kept in the order typed; a link's site is read from its address.
        from urllib.parse import urlparse
        for i, r in enumerate(clean):
            r["count"] = int(r.get("count") or 1) if path == "links" else int(r.get("count") or 0)
            r.setdefault("id", f"t{i}")
            if path == "links":
                r["domain"] = urlparse(r["url"]).netloc.replace("www.", "") if r.get("url") else None
        _s(snapshot)[path] = clean
        return True
    else:
        sort_key = spec["columns"][1][0]
        clean.sort(key=lambda r: r.get(sort_key, 0), reverse=True)
    snap = _s(snapshot)
    section, key = path.split(".", 1)
    block = dict(snap.get(section) or {})
    block[key] = clean
    snap[section] = block
    return True


def country_names(snapshot: dict) -> list[str]:
    """Every country either country slide could print, busiest first."""
    ga4 = _s(snapshot).get("ga4") or {}
    names: list[str] = []
    for key in ("countries", "countries_detail"):
        for row in ga4.get(key) or []:
            name = str((row or {}).get("country") or "").strip()
            if name and name not in names:
                names.append(name)
    sessions = country_sessions(snapshot)
    return sorted(names, key=lambda n: -sessions.get(n, 0))


def country_sessions(snapshot: dict) -> dict[str, float]:
    ga4 = _s(snapshot).get("ga4") or {}
    out: dict[str, float] = {}
    for key in ("countries_detail", "countries"):
        for row in ga4.get(key) or []:
            name = str((row or {}).get("country") or "").strip()
            if name and name not in out:
                out[name] = float(row.get("sessions") or 0)
    return out


def previous_value(snapshot: dict, section: str, key: str):
    """Last period's figure: as saved, or implied by the stored change. None
    when nothing says what it was."""
    snap = _s(snapshot)
    saved = ((snap.get("previous_values") or {}).get(section) or {})
    if saved.get(key) is not None:
        return float(saved[key])
    change = ((snap.get("kpi_deltas") or {}).get(section) or {}).get(key)
    if change is None:
        return None
    return float((snap.get(section) or {}).get(key) or 0) - float(change)


def rank_band_keys() -> list[str]:
    """The ranking slide's bands, keyed "top10", "11_20" … "none"."""
    from app.services.slide_deck import POSITION_BANDS
    return [key.split(".", 1)[1] for key, _, _ in POSITION_BANDS]


def rank_band_counts(keywords: list[dict], field: str) -> dict[str, int]:
    """How many keywords sit in each band, by `position` or `previous_position`,
    counted exactly as the slide counts them."""
    from app.services.slide_deck import POSITION_BANDS
    out = {key.split(".", 1)[1]: 0 for key, _, _ in POSITION_BANDS}
    for kw in keywords or []:
        pos = int(kw.get(field) or 0) or 10_000
        for key, lo, hi in POSITION_BANDS:
            if lo <= pos <= hi:
                out[key.split(".", 1)[1]] += 1
                break
    return out


def rank_bands_final(keywords: list[dict], overrides: Any = None) -> dict[str, dict[str, int | None]]:
    """Each band's count for this period, last period and the start — the
    figure typed in the builder where there is one, else worked out from the
    keywords. Last period and the start are None when nothing says what they were."""
    ov = clean_rank_overrides(overrides)["bands"]
    now = rank_band_counts(keywords, "position")
    has_prev = any(k.get("previous_position") for k in keywords or [])
    has_init = any(k.get("initial_rank") for k in keywords or [])
    prev = rank_band_counts([k for k in keywords or [] if k.get("previous_position")], "previous_position")
    init = rank_band_counts([k for k in keywords or [] if k.get("initial_rank")], "initial_rank")
    out = {}
    for key in rank_band_keys():
        cell = ov.get(key) or {}
        out[key] = {
            "now": cell.get("now", now[key]),
            "prev": cell.get("prev", prev[key] if has_prev else None),
            "initial": cell.get("initial", init[key] if has_init else None),
        }
    return out


def clean_rank_overrides(raw: Any) -> dict:
    """{"bands": {key: {"prev": n, "now": n}}, "moves": {"improved": n, "declined": n}},
    keeping only whole, non-negative numbers for known bands."""
    raw = raw if isinstance(raw, dict) else {}
    def num(v):
        try:
            n = int(float(v))
        except (TypeError, ValueError):
            return None
        return n if n >= 0 else None
    bands = {}
    for key in rank_band_keys():
        cell = (raw.get("bands") or {}).get(key) or {}
        kept = {side: num(cell.get(side)) for side in ("initial", "prev", "now") if num(cell.get(side)) is not None}
        if kept:
            bands[key] = kept
    moves = {k: num((raw.get("moves") or {}).get(k)) for k in ("improved", "declined")
             if num((raw.get("moves") or {}).get(k)) is not None}
    return {"bands": bands, "moves": moves}


def ranking_summary(keywords: list[dict], overrides: dict | None = None) -> dict:
    """The saved summary: the slide's bands folded into four, and movement,
    with any figure typed in the builder winning over the worked-out one."""
    overrides = clean_rank_overrides(overrides)
    now = rank_band_counts(keywords, "position")
    for key, cell in overrides["bands"].items():
        if "now" in cell:
            now[key] = cell["now"]
    out = {
        "top_10": now["top10"],
        "11_20": now["11_20"],
        "21_50": now["21_30"] + now["31_40"] + now["41_50"],
        "51_plus": now["51_100"],
        "improved": 0,
        "declined": 0,
    }
    for kw in keywords or []:
        n, w = int(kw.get("position") or 0), int(kw.get("previous_position") or 0)
        if n and w and n < w:
            out["improved"] += 1
        elif n and w and n > w:
            out["declined"] += 1
    out.update(overrides["moves"])
    return out


def write_initial_position(snapshot: dict, ident: str, value: float) -> bool:
    """Where one keyword started when tracking began; 0 clears it."""
    snap = _s(snapshot)
    rankings = dict(snap.get("rankings") or {})
    kws = list(rankings.get("keywords") or [])
    for idx, kw in enumerate(kws):
        if str(kw.get("keyword_id") or f"i{idx}") == ident:
            kw = dict(kw)
            kw["initial_rank"] = int(value) or None
            # "change" is measured from the start, so it follows the start.
            kw["change"] = (kw["initial_rank"] - int(kw.get("position") or 0)) \
                if kw["initial_rank"] and kw.get("position") else None
            kws[idx] = kw
            rankings["keywords"] = kws
            snap["rankings"] = rankings
            return True
    return False


def write_previous_lead(snapshot: dict, key: str, value: float) -> bool:
    """Last period's figure for one lead type (or the total; 0 on the total
    goes back to the sum of the four)."""
    if key not in {m["key"] for m in LEAD_KEYS} and key != "total":
        return False
    snap = _s(snapshot)
    block = dict(snap.get("ga4") or {})
    typed = dict(block.get("lead_overrides_previous") or {})
    number = max(0, int(value))
    if key == "total" and not number:
        typed.pop("total", None)
    else:
        typed[key] = number
    block["lead_overrides_previous"] = typed
    snap["ga4"] = block
    return True


def write_previous_position(snapshot: dict, ident: str, value: float) -> bool:
    """Last month's position for one keyword; 0 clears it."""
    snap = _s(snapshot)
    rankings = dict(snap.get("rankings") or {})
    kws = list(rankings.get("keywords") or [])
    for idx, kw in enumerate(kws):
        if str(kw.get("keyword_id") or f"i{idx}") == ident:
            kw = dict(kw)
            kw["previous_position"] = int(value) or None
            kws[idx] = kw
            rankings["keywords"] = kws
            snap["rankings"] = rankings
            return True
    return False


def previous_leads(snapshot: dict) -> dict[str, float | None]:
    """Last period's lead figures: typed in the builder, else found in last
    period's GA4 events when the report was built. None when unknown."""
    snap = _s(snapshot)
    typed = ((snap.get("ga4") or {}).get("lead_overrides_previous") or {})
    found = ((snap.get("previous_values") or {}).get("leads") or {})
    out: dict[str, float | None] = {}
    for meta in LEAD_KEYS:
        key = meta["key"]
        value = typed.get(key, found.get(key))
        out[key] = float(value) if value is not None else None
    known = [v for v in out.values() if v is not None]
    if typed.get("total"):
        out["total"] = float(typed["total"])
    elif found.get("total") is not None:
        out["total"] = float(found["total"])   # a several-month report's own baseline
    else:
        out["total"] = float(sum(known)) if known else None
    return out


def lead_values(snapshot: dict) -> dict[str, float]:
    """Each lead figure as the report will print it: typed in, or found in
    the GA4 event names."""
    from app.services.slide_deck import LEAD_FIGURES
    ga4 = _s(snapshot).get("ga4") or {}
    overrides = ga4.get("lead_overrides") or {}
    events = ga4.get("events") or {}
    out: dict[str, float] = {}
    for text_key, needles in LEAD_FIGURES:
        key = text_key.split(".", 1)[1]
        if key in overrides:
            out[key] = float(overrides[key] or 0)
        else:
            out[key] = float(sum(float(c or 0) for e, c in events.items()
                                 if any(n in e.lower() for n in needles)))
    return out


def _s(snapshot: Any) -> dict:
    return snapshot if isinstance(snapshot, dict) else {}


def checked_ai_rows(snapshot: dict) -> list[dict]:
    """This month's prompt checks. A draft opens with last month's answers
    marked unchecked; they count once the builder confirms or changes one."""
    return [r for r in (_s(snapshot).get("ai_visibility") or []) if isinstance(r, dict)]


def section_availability(snapshot: dict) -> dict[str, bool]:
    """Which sections actually carry something worth printing."""
    snap = _s(snapshot)
    gsc = snap.get("gsc") or {}
    ga4 = snap.get("ga4") or {}
    gbp = snap.get("gbp") or {}
    rankings = snap.get("rankings") or {}

    available = {
        "gsc": bool((gsc.get("clicks") or 0) or (gsc.get("impressions") or 0)),
        "ga4": bool((ga4.get("sessions") or 0) or (ga4.get("users") or 0)),
        "gbp": bool(
            (gbp.get("calls") or 0) or (gbp.get("direction_requests") or 0)
            or (gbp.get("website_clicks") or 0) or (gbp.get("bookings") or 0)
        ),
        "rankings": any(k.get("position") for k in rankings.get("keywords") or []),
        "ai_visibility": bool(checked_ai_rows(snap)),
        "links": bool(snap.get("links")),
        "work": bool(snap.get("activities") or snap.get("screenshots")),
    }
    return available


def enumerate_items(snapshot: dict, labels: dict[str, str] | None = None) -> list[dict]:
    """Every tickable datum in the snapshot, in presentation order.

    Each entry carries the id, its owning section, a human label, the current
    value, how to format it, and — for rows — the path needed to write an edit
    back into the snapshot.
    """
    snap = _s(snapshot)
    labels = labels or {}
    items: list[dict] = []

    months = ((snap.get("period") or {}).get("months") or 1)

    # ── Headline figures ──
    for section in ("gsc", "ga4", "gbp"):
        block = snap.get(section) or {}
        for meta in HEADLINE[section]:
            label = meta["label"]
            if section == "ga4" and meta["key"] == "users" and months > 1:
                label = "Avg. monthly users"
            items.append({
                "id": f"{section}.{meta['key']}",
                "section": section,
                "label": label,
                "value": block.get(meta["key"], 0) or 0,
                "format": meta["format"],
                "editable": True,
                # Google's own figures have no saved copy to correct;
                # Business Profile figures are kept by hand, so they do.
                "writable": section == "gbp",
                "kind": "headline",
            })

    # ── Last period's figure for each, typed or fetched, as its own item ──
    for section, keys in comparable_keys().items():
        for key in keys:
            meta = next((m for m in HEADLINE[section] if m["key"] == key), None) \
                or next((m for m in GBP_EXTRA if m["key"] == key), {"label": key})
            prev = previous_value(snap, section, key)
            items.append({
                "id": f"prev:{section}.{key}",
                "section": section,
                "label": meta.get("label", key),
                "value": prev if prev is not None else None,
                "format": meta.get("format", "int"),
                "editable": True,
                "writable": False,
                "kind": "previous",
                "pair": f"{section}.{key}",
            })

    # ── Leads & Conversion figures, and the Business Profile extras ──
    leads = lead_values(snap)
    typed_total = ((snap.get("ga4") or {}).get("lead_overrides") or {}).get("total")
    items.append({
        "id": "ga4.lead.total",
        "section": "ga4",
        "label": "Total leads" + ("" if typed_total else " — sum of the four below"),
        "value": typed_total or sum(leads.values()),
        "format": "int",
        "editable": True,
        "writable": False,
        "kind": "summary",
        "group": "Leads & Conversion — type a figure to replace what GA4 found; 0 hides it",
    })
    last = previous_leads(snap)
    for key in ["total"] + [m["key"] for m in LEAD_KEYS]:
        items.append({
            "id": f"prev:ga4.lead.{key}",
            "section": "ga4",
            "label": key,
            "value": last.get(key),
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "previous",
            "pair": f"ga4.lead.{key}",
        })
    for meta in LEAD_KEYS:
        items.append({
            "id": f"ga4.lead.{meta['key']}",
            "section": "ga4",
            "label": meta["label"],
            "value": leads.get(meta["key"], 0),
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "summary",
            "group": "Leads & Conversion — type a figure to replace what GA4 found; 0 hides it",
        })
    from app.services.slide_deck import AI_REFERRAL_ENGINES, ai_referral_traffic
    referral = {e["name"]: e["sessions"] for e in ai_referral_traffic(snap.get("ga4") or {})["engines"]}
    for name in AI_REFERRAL_ENGINES + [n for n in referral if n not in AI_REFERRAL_ENGINES]:
        items.append({
            "id": f"ga4.ai_ref.{name}",
            "section": "ga4",
            "label": name,
            "value": referral.get(name, 0),
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "summary",
            "group": "AI Assistant Referral Traffic — visits each assistant sent; 0 removes it",
        })
    gbp_block = snap.get("gbp") or {}
    for meta in GBP_EXTRA:
        items.append({
            "id": f"gbp.{meta['key']}",
            "section": "gbp",
            "label": meta["label"],
            "value": gbp_block.get(meta["key"], 0) or 0,
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "summary",
        })

    # ── Countries: one tickable row each, so any can be left out of the report ──
    for name in country_names(snap):
        items.append({
            "id": f"ga4.country.{name}",
            "section": "ga4",
            "label": name,
            "value": country_sessions(snap).get(name, 0),
            "format": "int",
            "editable": False,
            "writable": False,
            "kind": "row",
            "unit": "sessions",
        })

    # ── Rankings: summary figures, then one row per keyword ──
    rankings = snap.get("rankings") or {}
    summary = rankings.get("summary") or {}
    # The summary is worked out from the keywords' own positions (see
    # ranking_summary), so it is not listed as figures to type over.
    for idx, kw in enumerate(rankings.get("keywords") or []):
        ident = kw.get("keyword_id") or f"i{idx}"
        items.append({
            "id": f"rankings.kw.{ident}",
            "section": "rankings",
            "label": kw.get("term") or "(keyword)",
            "value": kw.get("position") or None,
            "format": "int",
            "editable": True,
            "writable": bool(kw.get("keyword_id")),
            "kind": "row",
            "unit": "position",
        })
        items.append({
            "id": f"init:rankings.kw.{ident}",
            "section": "rankings",
            "label": kw.get("term") or "(keyword)",
            "value": kw.get("initial_rank") or None,
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "initial",
            "pair": f"rankings.kw.{ident}",
            "unit": "position",
        })
        items.append({
            "id": f"prev:rankings.kw.{ident}",
            "section": "rankings",
            "label": kw.get("term") or "(keyword)",
            "value": kw.get("previous_position") or None,
            "format": "int",
            "editable": True,
            "writable": False,
            "kind": "previous",
            "pair": f"rankings.kw.{ident}",
            "unit": "position",
        })

    # ── AI visibility: one row per prompt/platform pair ──
    for idx, m in enumerate(snap.get("ai_visibility") or []):
        ident = f"{m.get('prompt_id') or idx}.{m.get('platform') or 'unknown'}"
        items.append({
            "id": f"ai_visibility.{ident}",
            "section": "ai_visibility",
            "label": f"{(m.get('platform') or 'unknown').replace('_', ' ')} · "
                     f"{m.get('prompt') or m.get('prompt_text') or labels.get(str(m.get('prompt_id')), 'prompt')}",
            "value": bool(m.get("mentioned")),
            "format": "bool",
            "editable": True,
            "writable": False,
            "kind": "row",
            "unit": "mentioned",
            "pending": bool(m.get("unchecked")),
        })

    # ── Links: one row per link ──
    for idx, link in enumerate(snap.get("links") or []):
        ident = link.get("id") or f"i{idx}"
        items.append({
            "id": f"links.{ident}",
            "section": "links",
            "label": f"{link.get('domain') or link.get('url') or 'link'} · {link.get('activity_type') or ''}".strip(" ·"),
            "value": link.get("count", 1) or 1,
            "format": "int",
            "editable": True,
            "writable": bool(link.get("id")),
            "kind": "row",
            "unit": "count",
        })

    # ── Work: activities then screenshots ──
    for idx, act in enumerate(snap.get("activities") or []):
        items.append({
            "id": f"work.act.{idx}",
            "section": "work",
            "label": act.get("activity_type") or "activity",
            "value": act.get("count", 0) or 0,
            "format": "int",
            "editable": True,
            "writable": bool(act.get("id")),
            "kind": "row",
            "unit": "count",
        })

    for idx, shot in enumerate(snap.get("screenshots") or []):
        ident = shot.get("id") or f"i{idx}"
        items.append({
            "id": f"work.shot.{ident}",
            "section": "work",
            "label": shot.get("caption") or f"Screenshot {idx + 1}",
            "value": None,
            "format": "none",
            "editable": False,
            "writable": False,
            "kind": "row",
        })

    return items


def all_item_ids(snapshot: dict) -> list[str]:
    return [i["id"] for i in enumerate_items(snapshot)]


def current_sections(snapshot: dict) -> dict[str, bool]:
    """Which sections print. Every one does, with data or without, unless a
    person switched it off — nothing is ever left out on the report's own."""
    stored = _s(snapshot).get("included_sections")
    stored = stored if isinstance(stored, dict) else {}
    return {k: bool(stored.get(k, True)) for k in SECTION_KEYS}


def current_items(snapshot: dict) -> dict[str, bool]:
    """Stored per-datum selection, defaulting to 'show everything'."""
    snap = _s(snapshot)
    stored = snap.get("included_items")
    ids = all_item_ids(snap)
    if not isinstance(stored, dict):
        return {i: True for i in ids}
    return {i: bool(stored.get(i, True)) for i in ids}


def apply_selection(snapshot: dict) -> dict:
    """A copy of the snapshot with unticked rows removed.

    Headline and summary figures are left in place — the templates hide those
    individually — but list rows are dropped here so every renderer sees the
    same, already-filtered arrays.
    """
    snap = dict(_s(snapshot))
    chosen = current_items(snap)
    # A report spanning several months: the earlier months' links and work,
    # as published, come before this month's.
    if snap.get("span_links"):
        snap["links"] = list(snap["span_links"]) + list(snap.get("links") or [])
    if snap.get("span_activities"):
        # One card per kind of task across the months, its counts added up —
        # the same task listed once for every month read as repetition.
        merged: dict[str, dict] = {}
        for act in list(snap["span_activities"]) + list(snap.get("activities") or []):
            name = str(act.get("activity_type") or "").strip()
            key = name.lower()
            if key not in merged:
                merged[key] = {"activity_type": name, "count": 0, "notes": act.get("notes")}
            merged[key]["count"] += int(act.get("count") or 0)
            if act.get("notes"):
                merged[key]["notes"] = act["notes"]
        snap["activities"] = list(merged.values())

    def keep(item_id: str) -> bool:
        return chosen.get(item_id, True)

    rankings = dict(snap.get("rankings") or {})
    if rankings.get("keywords"):
        rankings["keywords"] = [
            kw for idx, kw in enumerate(rankings["keywords"])
            if keep(f"rankings.kw.{kw.get('keyword_id') or f'i{idx}'}")
        ]
        snap["rankings"] = rankings

    # Countries left unticked drop out of both country slides — the donut,
    # the table and its total — for this period and the one compared with.
    ga4 = snap.get("ga4")
    if isinstance(ga4, dict):
        hidden = {n for n in country_names(snap) if not keep(f"ga4.country.{n}")}
        if hidden:
            ga4 = dict(ga4)
            for key in ("countries", "countries_detail", "countries_detail_previous"):
                if ga4.get(key):
                    ga4[key] = [r for r in ga4[key] if str((r or {}).get("country") or "").strip() not in hidden]
            snap["ga4"] = ga4

    if snap.get("ai_visibility"):
        snap["ai_visibility"] = [
            m for idx, m in enumerate(snap["ai_visibility"])
            if keep(f"ai_visibility.{m.get('prompt_id') or idx}.{m.get('platform') or 'unknown'}")
        ]

    if snap.get("links"):
        snap["links"] = [
            l for idx, l in enumerate(snap["links"])
            if keep(f"links.{l.get('id') or f'i{idx}'}")
        ]

    if snap.get("activities"):
        snap["activities"] = [
            a for idx, a in enumerate(snap["activities"]) if keep(f"work.act.{idx}")
        ]

    if snap.get("screenshots"):
        snap["screenshots"] = [
            s for idx, s in enumerate(snap["screenshots"])
            if keep(f"work.shot.{s.get('id') or f'i{idx}'}")
        ]

    return snap


def write_edit(snapshot: dict, item_id: str, value: Any) -> bool:
    """Write one edited value back into the snapshot. Returns True if applied."""
    snap = _s(snapshot)
    parts = item_id.split(".")

    if len(parts) == 2 and parts[0] in HEADLINE and parts[1] in {m["key"] for m in HEADLINE[parts[0]]}:
        section, key = parts
        block = dict(snap.get(section) or {})
        block[key] = float(value)
        snap[section] = block
        return True

    if item_id.startswith("ga4.lead."):
        key = item_id.split(".", 2)[2]
        if key not in {m["key"] for m in LEAD_KEYS} and key != "total":
            return False
        block = dict(snap.get("ga4") or {})
        overrides = dict(block.get("lead_overrides") or {})
        number = max(0, int(float(value)))
        if key == "total" and not number:
            overrides.pop("total", None)   # 0 goes back to the sum of the figures
        else:
            overrides[key] = number
        block["lead_overrides"] = overrides
        snap["ga4"] = block
        return True

    if item_id.startswith("ga4.ai_ref."):
        name = item_id.split(".", 2)[2].strip()
        if not name or len(name) > 40:
            return False
        block = dict(snap.get("ga4") or {})
        block["ai_referral_overrides"] = {**(block.get("ai_referral_overrides") or {}),
                                          name: max(0, int(float(value)))}
        snap["ga4"] = block
        return True

    if len(parts) == 2 and parts[0] == "gbp" and parts[1] in {m["key"] for m in GBP_EXTRA}:
        block = dict(snap.get("gbp") or {})
        block[parts[1]] = max(0.0, float(value))
        snap["gbp"] = block
        return True

    if item_id.startswith("rankings.summary."):
        key = item_id.split(".", 2)[2]
        if key not in {m["key"] for m in RANKING_SUMMARY}:
            return False
        rankings = dict(snap.get("rankings") or {})
        summary = dict(rankings.get("summary") or {})
        summary[key] = int(float(value))
        rankings["summary"] = summary
        snap["rankings"] = rankings
        return True

    if item_id.startswith("rankings.kw."):
        ident = item_id.split(".", 2)[2]
        rankings = dict(snap.get("rankings") or {})
        kws = list(rankings.get("keywords") or [])
        for idx, kw in enumerate(kws):
            if str(kw.get("keyword_id") or f"i{idx}") == ident:
                kw = dict(kw)
                kw["position"] = int(float(value))
                kws[idx] = kw
                rankings["keywords"] = kws
                snap["rankings"] = rankings
                return True
        return False

    if item_id.startswith("ai_visibility."):
        ident = item_id.split(".", 1)[1]
        rows = list(snap.get("ai_visibility") or [])
        for idx, m in enumerate(rows):
            if f"{m.get('prompt_id') or idx}.{m.get('platform') or 'unknown'}" == ident:
                m = dict(m)
                m["mentioned"] = bool(value)
                rows[idx] = m
                # One answer given means the grid has been looked at: every
                # answer in it now stands as this month's.
                snap["ai_visibility"] = [{k: v for k, v in r.items() if k != "unchecked"} for r in rows]
                return True
        return False

    if item_id.startswith("links."):
        ident = item_id.split(".", 1)[1]
        rows = list(snap.get("links") or [])
        for idx, l in enumerate(rows):
            if str(l.get("id") or f"i{idx}") == ident:
                l = dict(l)
                l["count"] = int(float(value))
                rows[idx] = l
                snap["links"] = rows
                return True
        return False

    if item_id.startswith("work.act."):
        try:
            idx = int(item_id.split(".")[2])
        except (ValueError, IndexError):
            return False
        rows = list(snap.get("activities") or [])
        if 0 <= idx < len(rows):
            row = dict(rows[idx])
            row["count"] = int(float(value))
            rows[idx] = row
            snap["activities"] = rows
            return True
        return False

    return False


# ── Editable copy ──────────────────────────────────────────────────────────
# Every heading can be retitled and given a subtitle, and the cover's brand
# line changed — as in the reference builder. Defaults are the template's own
# wording, so a report nobody touched reads exactly as it did before.

DEFAULT_BRAND_LINE = "Monthly SEO Report"

# Every heading the report prints, with the small label above it. Both are
# defaults: staff can rewrite either on any report, which is how a slide
# titled "Rankings" becomes "July was the strongest ranking month to date".
# Nothing in the template is written by hand — it all comes from here.
COPY_HEADINGS: list[dict[str, str]] = [
    # The order and the wording here are the report the agency agreed to
    # deliver, card by card. Anything reordered or renamed below changes the
    # deck itself, so it is edited deliberately and not for variety.
    # The cover. The key is historical (the deck once opened on an executive
    # summary); its title is the cover's big title and its subtitle the line
    # under it. The label above the title is the brand line, set on its own.
    {"key": "exec_summary", "section": "basics", "eyebrow": "", "title": "{client}", "label": "Cover"},
    {"key": "key_metrics", "section": "basics", "eyebrow": "This period", "title": "Performance Highlight"},
    {"key": "leads", "section": "ga4", "eyebrow": "Enquiries", "title": "Leads & Conversion"},
    {"key": "rankings", "section": "rankings", "eyebrow": "Keyword performance", "title": "Ranking Summary"},
    {"key": "rankings_table", "section": "rankings", "eyebrow": "Keyword performance", "title": "Keywords Rankings Tracking"},
    {"key": "ga4", "section": "ga4", "eyebrow": "Website traffic", "title": "Traffic Progress Summary"},
    {"key": "ga4_sources", "section": "ga4", "eyebrow": "Acquisition", "title": "Where the traffic came from"},
    {"key": "ga4_countries", "section": "ga4", "eyebrow": "Audience", "title": "Traffic (Geographical Distribution)"},
    {"key": "gsc", "section": "gsc", "eyebrow": "Search performance", "title": "Click & Impressions"},
    {"key": "gsc_console", "section": "gsc", "eyebrow": "Search performance", "title": "Search Console Performance"},
    {"key": "gsc_pages", "section": "gsc", "eyebrow": "Search performance", "title": "Top Performing Pages"},
    {"key": "ai_visibility", "section": "ai_visibility", "eyebrow": "Search generative experience", "title": "AI Keyword Visibility"},
    {"key": "ai_results", "section": "ai_visibility", "eyebrow": "Search generative experience", "title": "What the AI results tell us"},
    {"key": "ai_proof", "section": "ai_visibility", "eyebrow": "Proof of AI visibility", "title": "Where the assistants named you"},
    {"key": "ai_referral", "section": "ga4", "eyebrow": "Answer engines", "title": "AI Assistant Referral Traffic"},
    {"key": "gbp", "section": "gbp", "eyebrow": "Local search", "title": "Google Business Profile Performance"},
    {"key": "gbp_proof", "section": "gbp", "eyebrow": "Local search", "title": "Google Business Profile Highlights"},
    {"key": "links", "section": "links", "eyebrow": "Off-page SEO", "title": "Authority Building Through Backlinks"},
    {"key": "work", "section": "work", "eyebrow": "Action taken", "title": "Work Done & Proof"},
    {"key": "plan", "section": "basics", "eyebrow": "Way forward", "title": "Next Plan of Action"},
    {"key": "ga4_pages", "section": "ga4", "eyebrow": "Acquisition", "title": "Top landing pages"},
    {"key": "ga4_devices", "section": "ga4", "eyebrow": "Audience", "title": "Device breakdown"},
    {"key": "evidence", "section": "work", "eyebrow": "Evidence", "title": "Proof of work"},
    {"key": "closing", "section": "basics", "eyebrow": "Thank you", "title": "Let\u2019s keep {client} climbing the search results."},
]
_HEADING_DEFAULT = {h["key"]: h["title"] for h in COPY_HEADINGS}
_EYEBROW_DEFAULT = {h["key"]: h.get("eyebrow", "") for h in COPY_HEADINGS}

BRAND_LINE_MAX = 80
TITLE_MAX = 120
SUBTITLE_MAX = 280
EYEBROW_MAX = 60


def current_copy(snapshot: dict) -> dict:
    """The stored overrides only — anything absent means "use the default"."""
    stored = _s(snapshot).get("copy")
    stored = stored if isinstance(stored, dict) else {}

    def pick(field: str) -> dict[str, str]:
        raw = stored.get(field)
        raw = raw if isinstance(raw, dict) else {}
        return {k: str(v) for k, v in raw.items() if k in _HEADING_DEFAULT and str(v or "").strip()}

    from app.services import report_text

    return {
        "brand_line": str(stored.get("brand_line") or "").strip(),
        "eyebrows": pick("eyebrows"),
        "titles": pick("titles"),
        "subtitles": pick("subtitles"),
        "texts": report_text.current_texts(snapshot),
    }


def merge_copy(snapshot: dict, brand_line: str | None = None,
               titles: dict | None = None, subtitles: dict | None = None,
               eyebrows: dict | None = None, texts: dict | None = None) -> dict:
    """Apply an edit to the stored copy. A blank value clears that override,
    unknown headings are ignored, and every value is trimmed and capped."""
    copy = current_copy(snapshot)
    if brand_line is not None:
        copy["brand_line"] = str(brand_line).strip()[:BRAND_LINE_MAX]
    for field, incoming, limit in (
        ("titles", titles, TITLE_MAX),
        ("subtitles", subtitles, SUBTITLE_MAX),
        ("eyebrows", eyebrows, EYEBROW_MAX),
    ):
        if not isinstance(incoming, dict):
            continue
        for key, value in incoming.items():
            if key not in _HEADING_DEFAULT:
                continue
            text_ = str(value or "").strip()[:limit]
            if text_:
                copy[field][key] = text_
            else:
                copy[field].pop(key, None)

    if texts is not None:
        from app.services import report_text
        copy["texts"] = report_text.merge_texts(copy.get("texts") or {}, texts)

    return copy


def copy_text(copy: dict | None, key: str, field: str, tokens: dict[str, str] | None = None) -> str:
    """One piece of a heading — eyebrow, title or subtitle.

    The stored override wins; otherwise the default from COPY_HEADINGS. A
    subtitle has no default, so an unedited one prints nothing.
    """
    stored = copy.get(f"{field}s") if isinstance(copy, dict) else None
    text_ = str(stored.get(key) or "").strip() if isinstance(stored, dict) else ""
    if not text_ and field == "title":
        text_ = _HEADING_DEFAULT.get(key, "")
    if not text_ and field == "eyebrow":
        text_ = _EYEBROW_DEFAULT.get(key, "")
    for token, value in (tokens or {}).items():
        text_ = text_.replace(token, value)
    return text_


def brand_line(copy: dict | None) -> str:
    stored = str(copy.get("brand_line") or "").strip() if isinstance(copy, dict) else ""
    return stored or DEFAULT_BRAND_LINE


# ── Commentary blocks, derived from the headings above ──────────────────────

# The order the report prints these blocks in, which is the order the builder
# and the review list show them in too.
_BLOCK_ORDER = [
    "key_metrics", "leads",
    "rankings", "ga4", "ga4_countries",
    "gsc", "gsc_pages",
    "ai_visibility", "ai_referral",
    "gbp", "links", "work",
    "ga4_pages", "ga4_devices",
]

_BLOCKS_BY_KEY = {
    h["key"]: {"key": h["key"], "label": h["title"], "section": h["section"]}
    for h in COPY_HEADINGS if h["key"] not in NARRATION_EXCLUDED
}

NARRATION_BLOCKS: list[dict[str, str]] = [_BLOCKS_BY_KEY[k] for k in _BLOCK_ORDER]

NARRATION_KEYS = [b["key"] for b in NARRATION_BLOCKS]

# Every heading that can carry commentary must be in the order above, or a
# block would silently print with no way to write about it.
assert set(_BLOCKS_BY_KEY) == set(_BLOCK_ORDER), (
    f"commentary blocks out of sync: {set(_BLOCKS_BY_KEY) ^ set(_BLOCK_ORDER)}"
)

# Which blocks a report actually prints, and so which ones can be written about.
_BLOCK_NEEDS: dict[str, tuple[str, ...]] = {
    "key_metrics": ("gsc", "ga4", "gbp", "rankings", "ai_visibility"),
    # Leads belong to Analytics: they are its events, conversions, or figures typed in.
    "leads": ("ga4.events", "ga4.conversions", "ga4.lead_overrides"),
    "gsc_pages": ("gsc.trending_pages", "gsc.top_pages"),
    "ga4_sources": ("ga4.traffic_sources",),
    "ga4_pages": ("ga4.top_pages",),
    "ga4_devices": ("ga4.devices",),
    "ga4_countries": ("ga4.countries",),
    "ai_referral": ("ga4.traffic_sources",),
}


def narration_availability(snapshot: dict) -> dict[str, bool]:
    """Every commentary block, and whether the report has figures for it."""
    snap = _s(snapshot)
    sections = section_availability(snap)

    def has(path: str) -> bool:
        if "." not in path:
            return bool(sections.get(path))
        provider, key = path.split(".", 1)
        return bool((snap.get(provider) or {}).get(key))

    out: dict[str, bool] = {}
    for block in NARRATION_BLOCKS:
        needs = _BLOCK_NEEDS.get(block["key"])
        # A block with no special requirement rides on its own section.
        out[block["key"]] = any(has(n) for n in needs) if needs else bool(sections.get(block["key"]))
    return out



# ── The builder, slide by slide ─────────────────────────────────────────────
# Every slide the report can print, in the order it prints, with what feeds
# it. The builder draws itself from this list — steps, slide cards, the
# numbers on each, and the words on each — so it always matches the report.
#
# Parts are the numbers side of a slide:
#   figures  — figure ids (or a prefix), each with last month beside it
#   rows     — a list of rows (keywords, prompts, links…), each can be hidden
#   table    — one of LIST_SPECS, edited as rows
#   shots    — the slide's screenshot slots
#   months   — the month-by-month table of a multi-month report
#   editor   — a purpose-built editor the builder knows by name
# Words are the slide's heading (label, title, subtitle), its commentary
# paragraph, and any other wording printed on it.

STEPS = [
    {"key": "start", "label": "Cover", "about": "The reporting period, and the first page of the report."},
    {"key": "performance", "label": "Performance", "about": "The headline figures and the enquiries the site produced."},
    {"key": "rankings", "label": "Rankings", "about": "Where the tracked keywords rank this month."},
    {"key": "traffic", "label": "Website traffic", "about": "Google Analytics: visits, where they came from and where they are."},
    {"key": "search", "label": "Search", "about": "Google Search Console: clicks, impressions, queries and pages."},
    {"key": "ai", "label": "AI visibility", "about": "Whether AI assistants name the brand, and the visits they send."},
    {"key": "local", "label": "Local", "about": "The Google Business Profile."},
    {"key": "links_work", "label": "Links & work", "about": "Links built and work delivered this month."},
    {"key": "closing", "label": "Plan & close", "about": "What happens next, and the last page."},
]

SLIDES: list[dict] = [
    {"key": "cover", "name": "Cover", "step": "start", "section": None,
     "about": "The first page: the client's name, what they do, and the reporting period.",
     "parts": [{"type": "editor", "name": "brand_line", "label": "Brand line", "words": True,
                "hint": "The small gold label above the client's name."}],
     "heading": "exec_summary", "heading_fields": ["title", "subtitle"], "narration": None,
     "texts": ["cover.period_label", "cover.period", "cover.tags", "baseline.note"]},

    {"key": "key_metrics", "name": "Performance Highlight", "step": "performance", "section": None,
     "about": "The headline cards the report opens with, each compared with last month.",
     "parts": [{"type": "editor", "name": "kpi_cards", "label": "Cards on this slide",
                "hint": "Untick a card to leave it off. The numbers themselves are edited on their own slides further on."}],
     "heading": "key_metrics", "narration": "key_metrics", "texts": "block"},

    {"key": "leads", "name": "Leads & Conversion", "step": "performance", "section": "ga4",
     "about": "The enquiries: thank-you pages, email and phone clicks, transactions — and their total.",
     "parts": [{"type": "figures", "prefix": "ga4.lead.", "label": "Lead figures",
                "hint": "Filled from Google Analytics events. Type a number to replace it; 0 hides that box."}],
     "heading": "leads", "narration": "leads", "texts": "block"},

    {"key": "rankings", "name": "Ranking Summary", "step": "rankings", "section": "rankings",
     "about": "How many keywords sit in each position band, this month, last month and at the start.",
     "parts": [{"type": "editor", "name": "rank_summary", "label": "Ranking summary",
                "hint": "Worked out from the keywords on the next slide. Type a number to override a count."}],
     "heading": "rankings", "narration": "rankings", "texts": "block"},

    {"key": "rankings_table", "name": "Keywords Rankings Tracking", "step": "rankings", "section": "rankings",
     "about": "Every keyword's position: where it started, this month (with an arrow) and last month.",
     "parts": [{"type": "rows", "prefix": "rankings.kw.", "label": "Keywords",
                "hint": "Initial, last month and this month for each keyword. Untick one to leave it out."},
               {"type": "editor", "name": "add_keyword", "label": "Add a keyword", "hint": ""}],
     "heading": "rankings_table", "narration": None, "texts": "block"},

    {"key": "ga4", "name": "Traffic Progress Summary", "step": "traffic", "section": "ga4",
     "about": "Visits to the website, beside Google Analytics' traffic-by-channel table.",
     "parts": [{"type": "figures", "ids": ["ga4.sessions", "ga4.users", "ga4.engaged_sessions", "ga4.conversions", "ga4.revenue"],
                "label": "Headline figures", "hint": "Last month on the left, this month on the right."},
               {"type": "months", "section": "ga4", "label": "Month by month", "hint": ""},
               {"type": "table", "path": "ga4.channels", "label": "", "hint": ""},
               {"type": "table", "path": "ga4.channels_previous", "label": "", "hint": ""}],
     "heading": "ga4", "narration": "ga4", "texts": "block"},

    {"key": "ga4_countries", "name": "Traffic by country", "step": "traffic", "section": "ga4",
     "about": "Where visitors were: a share-of-visits donut and a users-by-country table.",
     "parts": [{"type": "rows", "prefix": "ga4.country.", "label": "Countries shown",
                "hint": "Untick a country to leave it out of the donut and the table."},
               {"type": "table", "path": "ga4.countries", "label": "", "hint": ""},
               {"type": "table", "path": "ga4.countries_detail", "label": "", "hint": ""},
               {"type": "table", "path": "ga4.countries_detail_previous", "label": "", "hint": ""}],
     "heading": "ga4_countries", "narration": "ga4_countries", "texts": "block"},

    {"key": "gsc", "name": "Click & Impressions", "step": "search", "section": "gsc",
     "about": "Clicks, impressions, click-through rate and average position from Google search.",
     "parts": [{"type": "figures", "ids": ["gsc.clicks", "gsc.impressions", "gsc.ctr", "gsc.position"],
                "label": "Headline figures", "hint": "Last month on the left, this month on the right."},
               {"type": "months", "section": "gsc", "label": "Month by month", "hint": ""}],
     "heading": "gsc", "narration": "gsc", "texts": "block"},

    {"key": "gsc_console", "name": "Search Console Performance", "step": "search", "section": "gsc",
     "about": "Search Console's own view: the four totals, the daily chart and the top queries.",
     "parts": [{"type": "table", "path": "gsc.top_queries", "label": "", "hint": ""}],
     "heading": "gsc_console", "narration": None, "texts": [],
     "note": "The totals and the daily chart use the Click & Impressions figures and Search Console's daily data."},

    {"key": "gsc_pages", "name": "Top Performing Pages", "step": "search", "section": "gsc",
     "about": "The pages gaining the most clicks against last month, each with its own picture.",
     "parts": [{"type": "table", "path": "gsc.trending_pages", "label": "", "hint": ""}],
     "heading": "gsc_pages", "narration": "gsc_pages", "texts": "block"},

    {"key": "ai_visibility", "name": "AI Keyword Visibility", "step": "ai", "section": "ai_visibility",
     "about": "Each tracked question, and whether each AI assistant names the brand for it.",
     "parts": [{"type": "rows", "prefix": "ai_visibility.", "label": "Prompt checks",
                "hint": "Mentioned or not found, per assistant. Untick one to leave it out."},
               {"type": "editor", "name": "add_prompt", "label": "Add a prompt", "hint": ""}],
     "heading": "ai_visibility", "narration": None, "texts": "block"},

    {"key": "ai_proof", "name": "Where the assistants named you", "step": "ai", "section": "ai_visibility",
     "about": "Screenshots of the AI assistants naming the brand.",
     "parts": [{"type": "shots", "section": "ai", "label": "AI answer screenshots",
                "hint": "Up to six. Paste (⌘V / Ctrl+V) or add — each is shown whole, whatever its size."}],
     "heading": "ai_proof", "narration": None, "texts": []},

    {"key": "ai_results", "name": "What the AI results tell us", "step": "ai", "section": "ai_visibility",
     "about": "The AI Visibility score, total mentions and cited pages, and each assistant's.",
     "parts": [{"type": "editor", "name": "ai_summary", "label": "AI results",
                "hint": "Worked out from the prompt checks where possible. Type any figure to replace it."}],
     "heading": "ai_results", "narration": "ai_visibility", "texts": []},

    {"key": "ai_referral", "name": "AI Assistant Referral Traffic", "step": "ai", "section": "ga4",
     "about": "Real visits from people who clicked through from an AI assistant.",
     "parts": [{"type": "figures", "prefix": "ga4.ai_ref.", "label": "Visits per assistant",
                "hint": "Found in Google Analytics' traffic sources. Type a number to replace it; 0 removes it."},
               {"type": "table", "path": "ga4.traffic_sources", "label": "", "hint": ""}],
     "heading": "ai_referral", "narration": "ai_referral", "texts": "block"},

    {"key": "gbp", "name": "Google Business Profile Performance", "step": "local", "section": "gbp",
     "about": "Calls, chats, website clicks, directions and bookings from the Business Profile.",
     "parts": [{"type": "figures", "ids": ["gbp.calls", "gbp.direction_requests", "gbp.website_clicks", "gbp.bookings", "gbp.chat_clicks"],
                "label": "Profile actions", "hint": "Last month on the left, this month on the right."},
               {"type": "months", "section": "gbp", "label": "Month by month", "hint": ""}],
     "heading": "gbp", "narration": "gbp", "texts": "block"},

    {"key": "gbp_proof", "name": "Google Business Profile Highlights", "step": "local", "section": "gbp",
     "about": "Screenshots from the Business Profile — posts, reviews, photos, insights.",
     "parts": [{"type": "shots", "section": "gbp", "label": "Business Profile screenshots",
                "hint": "Up to five. Paste (⌘V / Ctrl+V) or add — each is shown whole."}],
     "heading": "gbp_proof", "narration": None, "texts": []},

    {"key": "links", "name": "Backlinks", "step": "links_work", "section": "links",
     "about": "The links built this month, by type and by site.",
     "parts": [{"type": "table", "path": "links", "label": "", "hint": ""}],
     "heading": "links", "narration": "links", "texts": "block"},

    {"key": "work", "name": "Work Done & Proof", "step": "links_work", "section": "work",
     "about": "The work delivered this month, with proof.",
     "parts": [{"type": "table", "path": "activities", "label": "", "hint": ""}],
     "heading": "work", "narration": "work", "texts": "block"},

    {"key": "plan", "name": "Next Plan of Action", "step": "closing", "section": None,
     "about": "What the team does next: the next 30 days and the month after.",
     "parts": [{"type": "editor", "name": "plan", "label": "The plan", "words": True, "after_heading": True,
                "hint": "Drafted by AI from this report's figures. Edit any line."}],
     "heading": "plan", "narration": None, "texts": "block"},

    {"key": "closing", "name": "Thank you (last page)", "step": "closing", "section": None,
     "about": "The last page: a thank-you and how to get in touch.",
     "parts": [],
     "heading": "closing", "heading_fields": ["eyebrow", "title"], "narration": None, "texts": ["closing.note"]},
]


def slide_texts(slide: dict) -> list[str]:
    """The wording ids a slide prints, besides its heading and commentary."""
    from app.services import report_text
    if isinstance(slide.get("texts"), list):
        return list(slide["texts"])
    return [key for key, block, _, _ in report_text.TEXTS if block == slide["key"]]


def slide_status(snapshot: dict, images: dict[str, int] | None = None) -> dict[str, dict]:
    """Whether each slide will print, and if not, why — the same conditions
    the template uses, so the builder never promises a slide that is missing."""
    from app.services.slide_deck import ai_referral_traffic
    snap = _s(snapshot)
    images = images or {}
    on = current_sections(snap)
    hidden = set(snap.get("hidden_slides") or [])
    gsc, ga4, gbp = (snap.get("gsc") or {}), (snap.get("ga4") or {}), (snap.get("gbp") or {})
    keywords = (snap.get("rankings") or {}).get("keywords") or []
    ai_rows = checked_ai_rows(snap)
    plan = snap.get("next_month_plan") or {}
    narration = snap.get("narration") or {}

    def need(section: str | None, has: bool, empty_why: str) -> tuple[bool, str]:
        # A slide prints whether or not it has figures yet; the note only says
        # what is still missing. Only a switch a person turned off keeps it out.
        if section and not on.get(section):
            return False, "Its data section is switched off"
        return True, ("" if has else empty_why)

    def always(has: bool, empty_why: str) -> tuple[bool, str]:
        return True, ("" if has else empty_why)

    leads_has = sum(lead_values(snap).values()) > 0 or bool(ga4.get("conversions"))
    gbp_has = any((gbp.get(k) or 0) for k in ("calls", "direction_requests", "website_clicks", "bookings", "chat_clicks"))
    checks = {
        "cover": (True, ""),
        "key_metrics": always(any(on.values()), "Every data section is switched off"),
        "leads": need("ga4", leads_has, "No lead figures yet — add them below"),
        "rankings": need("rankings", any(k.get("position") for k in keywords),
                         "No positions yet — type this month's on the next slide" if keywords else "No keywords yet — add one on the next slide"),
        "rankings_table": need("rankings", any(k.get("position") for k in keywords),
                               "No positions yet — type this month's below" if keywords else "No keywords yet — add one below"),
        "ga4": need("ga4", bool(ga4.get("sessions") or ga4.get("users")), "No Analytics figures yet"),
        "ga4_countries": need("ga4", bool(ga4.get("countries")), "No country figures yet"),
        "gsc": need("gsc", bool(gsc.get("clicks") or gsc.get("impressions")), "No Search Console figures yet"),
        "gsc_console": need("gsc", bool(gsc.get("clicks") or gsc.get("impressions")), "No Search Console figures yet"),
        "gsc_pages": need("gsc", bool(gsc.get("trending_pages") or gsc.get("top_pages")), "No page figures yet"),
        "ai_visibility": need("ai_visibility", bool(ai_rows),
                              "Answers not confirmed yet — check the grid below" if snap.get("ai_visibility") else "No prompt checks yet — add one below"),
        "ai_proof": need("ai_visibility", bool(ai_rows) and bool(images.get("ai") or snap.get("screenshots")),
                         "No screenshots yet — add them below"),
        "ai_results": need("ai_visibility", bool(ai_rows) and bool(str(narration.get("ai_visibility") or "").strip() or snap.get("ai_summary")),
                           "No AI summary written yet"),
        "ai_referral": need("ga4", ai_referral_traffic(ga4)["sessions"] > 0, "No visits from AI assistants yet"),
        "gbp": need("gbp", gbp_has, "No Business Profile figures yet"),
        "gbp_proof": need("gbp", bool(images.get("gbp")), "No screenshots yet — add them below"),
        "links": need("links", bool(snap.get("links")), "No links recorded this month"),
        "work": need("work", bool(snap.get("activities")), "No work recorded this month"),
        "plan": always(bool(plan.get("now") or plan.get("next")), "No plan yet — it is drafted with AI"),
        "closing": (True, ""),
    }
    out = {}
    for slide in SLIDES:
        ok, why = checks.get(slide["key"], (True, ""))
        if slide["key"] in hidden:
            out[slide["key"]] = {"state": "hidden", "why": "Switched off — it won't print"}
        else:
            out[slide["key"]] = {"state": "in" if ok else "empty", "why": why}
    return out
