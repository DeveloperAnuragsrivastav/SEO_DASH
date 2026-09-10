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

RANKING_SUMMARY = [
    {"key": "top_10", "label": "Top 10"},
    {"key": "11_20", "label": "11–20"},
    {"key": "21_50", "label": "21–50"},
    {"key": "51_plus", "label": "51+"},
    {"key": "improved", "label": "Improved"},
    {"key": "declined", "label": "Declined"},
]


def _s(snapshot: Any) -> dict:
    return snapshot if isinstance(snapshot, dict) else {}


def section_availability(snapshot: dict) -> dict[str, bool]:
    """Which sections actually carry something worth printing."""
    snap = _s(snapshot)
    gsc = snap.get("gsc") or {}
    ga4 = snap.get("ga4") or {}
    gbp = snap.get("gbp") or {}
    rankings = snap.get("rankings") or {}

    return {
        "gsc": bool((gsc.get("clicks") or 0) or (gsc.get("impressions") or 0)),
        "ga4": bool((ga4.get("sessions") or 0) or (ga4.get("users") or 0)),
        "gbp": bool(
            (gbp.get("calls") or 0) or (gbp.get("direction_requests") or 0)
            or (gbp.get("website_clicks") or 0) or (gbp.get("bookings") or 0)
        ),
        "rankings": bool(rankings.get("keywords")),
        "ai_visibility": bool(snap.get("ai_visibility")),
        "links": bool(snap.get("links")),
        "work": bool(snap.get("activities") or snap.get("screenshots")),
    }


def enumerate_items(snapshot: dict, labels: dict[str, str] | None = None) -> list[dict]:
    """Every tickable datum in the snapshot, in presentation order.

    Each entry carries the id, its owning section, a human label, the current
    value, how to format it, and — for rows — the path needed to write an edit
    back into the snapshot.
    """
    snap = _s(snapshot)
    labels = labels or {}
    items: list[dict] = []

    # ── Headline figures ──
    for section in ("gsc", "ga4", "gbp"):
        block = snap.get(section) or {}
        for meta in HEADLINE[section]:
            items.append({
                "id": f"{section}.{meta['key']}",
                "section": section,
                "label": meta["label"],
                "value": block.get(meta["key"], 0) or 0,
                "format": meta["format"],
                "editable": True,
                "kind": "headline",
            })

    # ── Rankings: summary figures, then one row per keyword ──
    rankings = snap.get("rankings") or {}
    summary = rankings.get("summary") or {}
    for meta in RANKING_SUMMARY:
        items.append({
            "id": f"rankings.summary.{meta['key']}",
            "section": "rankings",
            "label": meta["label"],
            "value": summary.get(meta["key"], 0) or 0,
            "format": "int",
            "editable": True,
            "kind": "summary",
        })

    for idx, kw in enumerate(rankings.get("keywords") or []):
        ident = kw.get("keyword_id") or f"i{idx}"
        items.append({
            "id": f"rankings.kw.{ident}",
            "section": "rankings",
            "label": kw.get("term") or "(keyword)",
            "value": kw.get("position", 0) or 0,
            "format": "int",
            "editable": True,
            "kind": "row",
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
            "kind": "row",
            "unit": "mentioned",
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
            "kind": "row",
        })

    return items


def all_item_ids(snapshot: dict) -> list[str]:
    return [i["id"] for i in enumerate_items(snapshot)]


def current_sections(snapshot: dict) -> dict[str, bool]:
    """Stored section selection, defaulting to 'everything that has data'."""
    snap = _s(snapshot)
    available = section_availability(snap)
    stored = snap.get("included_sections")
    if not isinstance(stored, dict):
        return available
    return {k: bool(stored.get(k, available[k])) and available[k] for k in SECTION_KEYS}


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

    def keep(item_id: str) -> bool:
        return chosen.get(item_id, True)

    rankings = dict(snap.get("rankings") or {})
    if rankings.get("keywords"):
        rankings["keywords"] = [
            kw for idx, kw in enumerate(rankings["keywords"])
            if keep(f"rankings.kw.{kw.get('keyword_id') or f'i{idx}'}")
        ]
        snap["rankings"] = rankings

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

    if len(parts) == 2 and parts[0] in HEADLINE:
        section, key = parts
        if key not in {m["key"] for m in HEADLINE[section]}:
            return False
        block = dict(snap.get(section) or {})
        block[key] = float(value)
        snap[section] = block
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
                snap["ai_visibility"] = rows
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
