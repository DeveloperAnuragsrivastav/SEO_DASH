"""Fill a draft's Search Console and Analytics figures from screenshots.

For people who cannot connect GA4 or Search Console: they upload a screenshot
of the report Google shows them, the AI transcribes what is on it, and the
figures land in the same places the builder's own boxes and tables write to.

Nothing here is strict. A screenshot is read for whatever it shows, and every
figure stays editable. Anything that needs checking — a date range one day
off, a total Google rounded, a figure worked out rather than read — comes back
as a notice for the person, not as a refusal.

The AI only transcribes (text as printed); every number is parsed and every
column mapped here, so a misread header can never land in the wrong field.
"""
from __future__ import annotations

import base64
import datetime
import json
import re
from typing import Any, Optional

import httpx

from app.config import settings
from app.services import report_composer as composer
from app.services.openai_service import OPENAI_API_URL

# Sample screenshots, served by the frontend from /samples/. Each is the
# screen to open, set to this report's dates, and what it fills.
SAMPLES: dict[str, dict[str, str]] = {
    "gsc_compare": {
        "file": "gsc-performance-compare.webp",
        "title": "Search Console · Performance (Compare)",
        "how": "Performance → Search results → Date → Compare: this period against the one before.",
    },
    "gsc_performance": {
        "file": "gsc-performance.webp",
        "title": "Search Console · Performance",
        "how": "Performance → Search results → Date → Custom: this period.",
    },
    "gsc_queries": {
        "file": "gsc-queries.webp",
        "title": "Search Console · Queries tab",
        "how": "Performance → Search results, scroll to the table, Queries tab.",
    },
    "gsc_pages": {
        "file": "gsc-pages.webp",
        "title": "Search Console · Pages tab",
        "how": "Performance → Search results, scroll to the table, Pages tab.",
    },
    "ga4_events": {
        "file": "ga4-events.png",
        "title": "Analytics · Events",
        "how": "Reports → Engagement → Events.",
    },
    "ga4_channels": {
        "file": "ga4-traffic-acquisition.webp",
        "title": "Analytics · Traffic acquisition",
        "how": "Reports → Acquisition → Traffic acquisition (by channel group).",
    },
    "ga4_countries": {
        "file": "ga4-country.webp",
        "title": "Analytics · Demographic details (Country)",
        "how": "Reports → User attributes → Demographic details, first column Country.",
    },
}

# The slide each kind of screen fills, for "this filled X, not Y".
SCREEN_SLIDE = {
    "gsc_totals": "gsc", "gsc_queries": "gsc_console", "gsc_pages": "gsc_pages",
    "ga4_channels": "ga4", "ga4_countries": "ga4_countries", "ga4_events": "leads",
    "ga4_sources": "ai_referral",
}
SLIDE_NAME = {s["key"]: s["name"] for s in composer.SLIDES}


class ShotError(ValueError):
    """The screenshot cannot be used; the message says why and what to do."""


# ── Reading ────────────────────────────────────────────────────────────────

def _prompt(current: tuple[datetime.date, datetime.date], previous: tuple[datetime.date, datetime.date]) -> str:
    def iso(w):
        return f"{w[0].isoformat()} to {w[1].isoformat()}"
    return (
        "You transcribe screenshots of Google Search Console and Google Analytics 4 reports. "
        "Copy exactly what is visible; never calculate, round or invent a figure.\n"
        f"Context: the report being filled covers {iso(current)}, compared with {iso(previous)}. "
        "Dates on screen may be day-first (05/09/2026 = 5 September 2026) or month-first. Pick the reading "
        "the screen itself supports (a day above 12, a month name, the chart's axis); if it is still "
        "ambiguous, the reading closest to the report's dates.\n"
        "Return JSON only, shaped as:\n"
        "{\n"
        '  "product": "gsc" | "ga4" | "other",\n'
        '  "screen": "the report title as shown, e.g. Performance, Traffic acquisition: Session primary channel group, '
        'Demographic details: Country, Events: Event name",\n'
        '  "date_ranges": [{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "label": "as printed"}],\n'
        '  "scorecards": [{"range": 0, "metric": "Total clicks", "value": "123"}],\n'
        '  "table": {\n'
        '    "dimension": "the first column header, e.g. Top queries, Top pages, Country, Event name, Session primary channel group",\n'
        '    "columns": ["each metric column header, left to right, as printed"],\n'
        '    "total": [{"range": 0, "values": {"<column header>": "<as printed>"}}],\n'
        '    "rows": [{"name": "<first column text>", "range": 0, "values": {"<column header>": "<as printed>"}}],\n'
        '    "complete": true\n'
        "  }\n"
        "}\n"
        "Rules:\n"
        "- date_ranges: the period(s) the figures cover, from the date picker or the scorecards. When two are "
        "compared, put the newer one first. Empty list if no dates are visible.\n"
        "- range: the index in date_ranges a figure belongs to (0 when there is one range).\n"
        "- scorecards: Search Console's big total boxes (Total clicks, Total impressions, Average CTR, Average "
        "position) — one entry per metric per range. GA4 has none; use []. \n"
        "- Values exactly as printed, as strings: \"1,132\", \"93.6k\", \"19.71%\", \"1m 04s\", \"287 (44.7%)\", \"$0.00\".\n"
        "- Compare mode: a Search Console table has one column per range (two Clicks columns…) — give one row "
        "object per range. A GA4 table prints each row's figures per range on separate lines — give one row object "
        "per range. Skip difference / change / % change columns.\n"
        "- total: GA4's Total row (one per range). Omit when not shown.\n"
        "- rows: every row visible in the main table, top to bottom, up to 300. Do not include the Total row.\n"
        "- complete: false when rows are cut off at the edge of the screenshot.\n"
        "- If the image is not a Search Console or Analytics report, or nothing can be read: product \"other\", "
        "everything else empty."
    )


def read_image(image: bytes, mime: str, current: tuple[datetime.date, datetime.date],
               previous: tuple[datetime.date, datetime.date]) -> dict:
    """The AI's transcription of one screenshot (see _prompt for its shape)."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration.")
    payload = {
        "model": "gpt-4o",
        "temperature": 0,
        "max_tokens": 16000,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": _prompt(current, previous)},
            {"type": "image_url", "image_url": {
                "url": f"data:{mime};base64,{base64.b64encode(image).decode()}", "detail": "high"}},
        ]}],
    }
    with httpx.Client(timeout=120.0) as client:
        res = client.post(OPENAI_API_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        res.raise_for_status()
    content = ((res.json().get("choices") or [{}])[0].get("message") or {}).get("content")
    try:
        data = json.loads(content) if content else {}
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def image_size(data: bytes) -> Optional[tuple[int, int]]:
    """Width and height of a PNG, JPEG or WebP from its own header."""
    import struct
    try:
        if data.startswith(b"\x89PNG"):
            return struct.unpack(">II", data[16:24])
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
            if chunk == b"VP8L":
                b = int.from_bytes(data[21:25], "little")
                return 1 + (b & 0x3FFF), 1 + ((b >> 14) & 0x3FFF)
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
        if data.startswith(b"\xff\xd8"):
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except (struct.error, IndexError):
        return None
    return None


def size_notice(data: bytes) -> Optional[dict]:
    """A screenshot too small to read reliably: the AI can misread, or
    invent, figures it cannot make out."""
    size = image_size(data)
    if size and size[0] < 900:
        return {"level": "warning", "text":
            f"The screenshot is small ({size[0]}×{size[1]} pixels), so some figures may be misread. Check every "
            "figure against it — or take it on a wider window, without zooming out."}
    return None


# ── Numbers as Google prints them ──────────────────────────────────────────

_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}


def number(text: Any) -> tuple[Optional[float], bool]:
    """A printed figure as a number, and whether Google rounded it (93.6k).
    "287 (44.7%)" is 287; "19.71%" is 19.71; "—" and "(not set)" are None."""
    if isinstance(text, bool) or text is None:
        return None, False
    if isinstance(text, (int, float)):
        return float(text), False
    s = str(text).strip()
    s = re.sub(r"\s*\(.*?\)\s*$", "", s)               # the share beside a figure
    s = s.replace(",", "").replace(" ", "").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"^[^\d.\-]+", "", s)                    # $, ₹, €, £…
    s = s.rstrip("%")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)([kKmMbB]?)", s)
    if not m:
        return None, False
    value = float(m.group(1))
    suffix = m.group(2).lower()
    if suffix:
        return value * _SUFFIX[suffix], True
    return value, False


def duration(text: Any) -> Optional[float]:
    """GA4's durations in seconds: "12s", "1m 04s", "1h 2m 3s", "00:01:04"."""
    if text is None:
        return None
    s = str(text).strip().lower()
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", s):
        parts = [int(p) for p in s.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    found = re.findall(r"(\d+(?:\.\d+)?)\s*([hms])", s)
    if found:
        return float(sum(float(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in found))
    value, _ = number(s)
    return value


# GA4 column headers → the field they hold. Exact names first; the longer
# ones are matched before any shorter one they contain.
_GA4_HEADERS: list[tuple[str, str]] = [
    ("event count per active user", "_skip"),
    ("engaged sessions per active user", "eng_per_user"),
    ("engaged sessions per user", "eng_per_user"),
    ("average engagement time per active user", "time_per_user"),
    ("average engagement time per session", "time_per_session"),
    ("average engagement time", "time_per_user"),
    ("views per active user", "_skip"),
    ("events per session", "events_per_session"),
    ("engaged sessions", "engaged_sessions"),
    ("engagement rate", "engagement_rate"),
    ("event count", "event_count"),
    ("key events", "key_events"),
    ("conversions", "key_events"),
    ("total revenue", "revenue"),
    ("purchase revenue", "revenue"),
    ("revenue", "revenue"),
    ("active users", "active_users"),
    ("new users", "new_users"),
    ("total users", "total_users"),
    ("sessions", "sessions"),
    ("views", "views"),
]


def _ga4_field(header: str) -> Optional[str]:
    h = re.sub(r"\s+", " ", str(header or "").lower()).strip()
    for name, field in _GA4_HEADERS:
        if h == name:
            return None if field == "_skip" else field
    for name, field in _GA4_HEADERS:
        if name in h:
            return None if field == "_skip" else field
    return None


def _ga4_values(values: dict) -> dict[str, float]:
    """One GA4 row's printed values as fields, durations in seconds and rates
    as fractions."""
    out: dict[str, float] = {}
    for header, raw in (values or {}).items():
        field = _ga4_field(header)
        if not field or field in out:
            continue
        if field.startswith("time_"):
            v = duration(raw)
        else:
            v, _ = number(raw)
            if v is not None and field == "engagement_rate":
                v = v / 100
        if v is not None and v >= 0:
            out[field] = v
    return out


def _gsc_field(header: str) -> Optional[str]:
    h = str(header or "").lower()
    for key in ("clicks", "impressions", "ctr", "position"):
        if key in h:
            return key
    return None


# ── Dates ──────────────────────────────────────────────────────────────────

def _date(text: Any) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(str(text)[:10])
    except (TypeError, ValueError):
        return None


def _overlap(a: tuple[datetime.date, datetime.date], b: tuple[datetime.date, datetime.date]) -> int:
    return max(0, (min(a[1], b[1]) - max(a[0], b[0])).days + 1)


def _swapped(r: tuple[datetime.date, datetime.date]) -> Optional[tuple[datetime.date, datetime.date]]:
    """The same range read the other way round (05/09 as 9 May, not 5 Sep)."""
    try:
        s = datetime.date(r[0].year, r[0].day, r[0].month)
        e = datetime.date(r[1].year, r[1].day, r[1].month)
    except ValueError:
        return None
    return (min(s, e), max(s, e))


def _fmt(d: datetime.date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def _span(r: tuple[datetime.date, datetime.date]) -> str:
    return f"{_fmt(r[0])} – {_fmt(r[1])}"


def _days(n: int) -> str:
    return f"{n} day{'s' if n != 1 else ''}"


def _ranges(read: dict, windows: dict) -> list[tuple[datetime.date, datetime.date]]:
    out = []
    for r in (read.get("date_ranges") or [])[:2]:
        if not isinstance(r, dict):
            continue
        s, e = _date(r.get("start")), _date(r.get("end"))
        if not s or not e:
            continue
        rng = (min(s, e), max(s, e))
        # A day-first date read month-first lands months away from the report;
        # the other reading is taken when only it fits.
        if not any(_overlap(rng, w) for w in windows.values()):
            alt = _swapped((s, e))
            if alt and any(_overlap(alt, w) for w in windows.values()):
                rng = alt
        out.append(rng)
    return out


def assign_periods(read: dict, windows: dict, force: Optional[str], notices: list) -> dict[int, str]:
    """Which of the report's periods ("current", "previous") each date range
    on the screenshot is, with a notice for every range that does not match
    its period exactly. Never refuses: an unreadable or unrelated range is
    filled as this period (or the one asked for), and said so."""
    ranges = _ranges(read, windows)
    out: dict[int, str] = {}
    if not ranges:
        which = force or "current"
        notices.append({"level": "warning", "text":
            f"The dates aren't visible on the screenshot, so it was filled as "
            f"{'last period' if which == 'previous' else 'this period'} ({_span(windows[which])}). "
            "Check that is the period it shows."})
        return {0: which}
    if len(ranges) == 1:
        if force:
            out[0] = force
        else:
            cur, prev = (_overlap(ranges[0], windows["current"]), _overlap(ranges[0], windows["previous"]))
            out[0] = "previous" if prev > cur else "current"
            if not cur and not prev:
                notices.append({"level": "warning", "text":
                    f"The screenshot covers {_span(ranges[0])}, which is neither this period "
                    f"({_span(windows['current'])}) nor last period ({_span(windows['previous'])}). "
                    "It was filled as this period anyway — check it is the right screenshot, or re-take it with "
                    "this period's dates."})
                return out
    else:
        a, b = ranges
        straight = _overlap(a, windows["current"]) + _overlap(b, windows["previous"])
        crossed = _overlap(a, windows["previous"]) + _overlap(b, windows["current"])
        out = {0: "previous", 1: "current"} if crossed > straight else {0: "current", 1: "previous"}
    for idx, which in out.items():
        if idx < len(ranges):
            _date_notice(ranges[idx], windows[which], which, notices)
    return out


def _date_notice(rng, window, which: str, notices: list) -> None:
    if rng == window:
        return
    name = "this period" if which == "current" else "last period"
    extra = max(0, (window[0] - rng[0]).days) + max(0, (rng[1] - window[1]).days)
    short = max(0, (rng[0] - window[0]).days) + max(0, (window[1] - rng[1]).days)
    if not _overlap(rng, window):
        # Filled into a period it does not touch: only when asked to.
        notices.append({"level": "warning", "text":
            f"The screenshot covers {_span(rng)}, but {name} is {_span(window)}. It was filled as {name} "
            "because you chose it — check the figures."})
        return
    bits = []
    if extra:
        bits.append(f"{_days(extra)} more")
    if short:
        bits.append(f"{_days(short)} fewer")
    notices.append({"level": "warning", "text":
        f"{name.capitalize()} is {_span(window)}, but the screenshot covers {_span(rng)} — "
        f"{' and '.join(bits)} than the report. The figures were filled in anyway: please check and edit them, "
        f"or re-take the screenshot for {_span(window)}."})


# ── What a screenshot is ───────────────────────────────────────────────────

def classify(read: dict) -> list[str]:
    """The kinds of figures the screenshot holds (it can be several: Search
    Console's totals above its queries table)."""
    product = str(read.get("product") or "").lower()
    table = read.get("table") if isinstance(read.get("table"), dict) else {}
    dim = str(table.get("dimension") or "").lower()
    screen = str(read.get("screen") or "").lower()
    has_rows = bool(table.get("rows") or table.get("total"))
    kinds: list[str] = []
    if product == "gsc":
        if any(_gsc_field(c.get("metric")) for c in read.get("scorecards") or [] if isinstance(c, dict)):
            kinds.append("gsc_totals")
        if has_rows:
            if "quer" in dim:
                kinds.append("gsc_queries")
            elif "page" in dim:
                kinds.append("gsc_pages")
            elif dim:
                kinds.append("gsc_other")
    elif product == "ga4" and has_rows:
        what = dim or screen
        if "channel" in what:
            kinds.append("ga4_channels")
        elif "countr" in what:
            kinds.append("ga4_countries")
        elif "event" in what:
            kinds.append("ga4_events")
        elif "source" in what:
            kinds.append("ga4_sources")
        else:
            # Pages and screens, Browser, Device… — no slide prints these.
            kinds.append("ga4_other")
    return kinds


# ── Filling the draft ──────────────────────────────────────────────────────

def _rows_for(table: dict, idx: int) -> list[dict]:
    return [r for r in table.get("rows") or [] if isinstance(r, dict)
            and int(r.get("range") or 0) == idx and str(r.get("name") or "").strip()]


def _total_for(table: dict, idx: int) -> Optional[dict]:
    for t in table.get("total") or []:
        if isinstance(t, dict) and int(t.get("range") or 0) == idx:
            return t.get("values") or {}
    return None


def _put_rows(snapshot: dict, path: str, rows: list[dict], complete: bool) -> None:
    """A table read off a screenshot. A full table replaces what is there;
    one or two rows (a table cut off at the bottom of the screen) are added
    to it, by name, instead of wiping the rest. Fields the screenshot does
    not carry (a page's picture) are kept from the row it replaces."""
    spec = composer._LIST_BY_PATH[path]
    key = spec["columns"][0][0]
    existing = {str(r.get(key)): r for r in composer.list_rows(snapshot, path)}
    rows = [{**{k: v for k, v in existing.get(str(r[key]), {}).items() if k not in r}, **r} for r in rows]
    if not complete and len(rows) < 3:
        names = {str(r[key]) for r in rows}
        rows = rows + [r for name, r in existing.items() if name not in names]
    composer.write_list(snapshot, path, rows)


def fill(snapshot: dict, read: dict, windows: dict, force: Optional[str] = None,
         slide: Optional[str] = None) -> dict:
    """Write what the screenshot shows into the draft.

    Tables and events are written straight into `snapshot`; the headline
    figures come back as `edits` ({"gsc.clicks": 133, "prev:gsc.clicks": 123})
    for the builder's own figure-editing path, so a figure read off a
    screenshot behaves exactly as one typed into its box.
    """
    kinds = classify(read)
    if not kinds or str(read.get("product") or "").lower() not in ("gsc", "ga4"):
        raise ShotError("This doesn't look like a Search Console or Google Analytics report, so nothing was filled. "
                        "Download the sample beside the upload button to see which screen to use.")
    used = [k for k in kinds if k in SCREEN_SLIDE]
    if not used:
        what = (read.get("table") or {}).get("dimension") or read.get("screen") or "this screen"
        raise ShotError(f"The screenshot was read ({what}), but the report has no slide for it, so nothing was "
                        "filled. Download the sample beside the upload button to see which screen this slide needs.")

    notices: list[dict] = []
    periods = assign_periods(read, windows, force, notices)
    dated = len(notices)          # notices after this one are about the figures
    table = read.get("table") if isinstance(read.get("table"), dict) else {}
    complete = bool(table.get("complete"))
    edits: dict[str, float] = {}
    filled: list[str] = []
    rounded: set[str] = set()

    def edit(which: str, key: str, value: Optional[float]) -> None:
        if value is None or value < 0:
            return
        edits[("prev:" if which == "previous" else "") + key] = value

    if "gsc_totals" in kinds:
        for idx, which in periods.items():
            got: dict[str, float] = {}
            for card in read.get("scorecards") or []:
                if not isinstance(card, dict) or int(card.get("range") or 0) != idx:
                    continue
                field = _gsc_field(card.get("metric"))
                v, was_rounded = number(card.get("value"))
                if field and v is not None and field not in got:
                    got[field] = v
                    if was_rounded:
                        rounded.add(f"{card.get('metric') or field} ({card.get('value')})")
            if not got:
                continue
            # CTR from clicks and impressions is exact; the card shows 0.1%.
            if got.get("impressions") and "clicks" in got:
                got["ctr"] = got["clicks"] / got["impressions"]
            elif "ctr" in got:
                got["ctr"] = got["ctr"] / 100
            for field in ("clicks", "impressions", "ctr", "position"):
                edit(which, f"gsc.{field}", got.get(field))
            filled.append(f"Search Console totals for {'this' if which == 'current' else 'last'} period")

    if "gsc_queries" in kinds:
        for idx, which in periods.items():
            rows = _gsc_rows(_rows_for(table, idx), "query")
            if not rows:
                continue
            if which == "previous":
                notices.append({"level": "info", "text":
                    "The report shows this period's queries only, so last period's were not used."})
                continue
            _put_rows(snapshot, "gsc.top_queries", rows, complete)
            filled.append(f"{len(rows)} search quer{'y' if len(rows) == 1 else 'ies'}")

    if "gsc_pages" in kinds:
        by_period = {which: _gsc_rows(_rows_for(table, idx), "page") for idx, which in periods.items()}
        now, before = by_period.get("current") or [], by_period.get("previous") or []
        before_clicks = {r["page"]: r.get("clicks", 0) for r in before}
        if now:
            had = {r.get("page"): r.get("prev_clicks") for r in composer.list_rows(snapshot, "gsc.trending_pages")}
            rows = []
            for r in now:
                prev = before_clicks.get(r["page"], had.get(r["page"]))
                rows.append({**r, **({"prev_clicks": prev} if prev is not None else {})})
            _put_rows(snapshot, "gsc.trending_pages", rows, complete)
            filled.append(f"{len(rows)} page{'s' if len(rows) != 1 else ''}")
            if not before and not any(v for v in had.values()):
                notices.append({"level": "info", "text":
                    "Last period's clicks per page aren't on this screenshot. Upload last period's Pages tab too "
                    "(or a Compare screenshot), or type them in the table."})
        elif before:
            rows = composer.list_rows(snapshot, "gsc.trending_pages")
            if not rows:
                notices.append({"level": "warning", "text":
                    "This is last period's Pages tab. Upload this period's first — the slide lists this period's "
                    "pages, with last period's clicks beside them."})
            else:
                matched = 0
                for r in rows:
                    if r.get("page") in before_clicks:
                        r["prev_clicks"] = before_clicks[r["page"]]
                        matched += 1
                composer.write_list(snapshot, "gsc.trending_pages", rows)
                filled.append(f"last period's clicks for {matched} page{'s' if matched != 1 else ''}")

    corrected: list[str] = []
    missing: set[str] = set()
    if "ga4_channels" in kinds or "ga4_countries" in kinds:
        country = "ga4_countries" in kinds
        name_key, path = ("country", "ga4.countries_detail") if country else ("channel", "ga4.channels")
        for idx, which in periods.items():
            rows = []
            estimated = False
            for r in _rows_for(table, idx):
                name = str(r["name"]).strip()
                vals = _ga4_values(r.get("values") or {})
                fixed = _check_engaged(vals)
                if fixed:
                    corrected.append(f"{name} ({fixed})")
                row, guessed = _ga4_row(vals, country)
                estimated = estimated or guessed
                rows.append({name_key: name, **row})
            if not rows:
                continue
            _put_rows(snapshot, path + ("_previous" if which == "previous" else ""), rows, complete)
            if country and which == "current":
                _put_rows(snapshot, "ga4.countries", [{"country": r["country"], "sessions": r.get("sessions", 0)} for r in rows], complete)
            labels = {f: l for f, l, _ in composer._LIST_BY_PATH[path]["columns"][1:]}
            missing.update(labels[f] for f in labels if not any(f in r for r in rows))
            total = _ga4_values(_total_for(table, idx) or {})
            fixed = _check_engaged(total)
            if fixed:
                corrected.append(f"Total ({fixed})")
            if not total and complete:
                total = {f: sum(r.get(f, 0) for r in rows) for f in ("sessions", "engaged_sessions", "key_events", "revenue")
                         if any(f in r for r in rows)}
            if country:
                edit(which, "ga4.users", total.get("active_users"))
            else:
                edit(which, "ga4.sessions", total.get("sessions"))
                if "active_users" in total:
                    edit(which, "ga4.users", total.get("active_users"))
            edit(which, "ga4.engaged_sessions", total.get("engaged_sessions"))
            edit(which, "ga4.conversions", total.get("key_events"))
            edit(which, "ga4.revenue", total.get("revenue"))
            filled.append(f"{len(rows)} {'countries' if country else 'channels'} for {'this' if which == 'current' else 'last'} period")
            if estimated:
                notices.append({"level": "info", "text":
                    "The Country screen has no Sessions column, so each country's sessions were worked out "
                    "(engaged sessions ÷ engagement rate, or its users where none were engaged). Check the "
                    "sessions donut, or type the real figures in the table."})

    if "ga4_events" in kinds:
        for idx, which in periods.items():
            events: dict[str, float] = {}
            for r in _rows_for(table, idx):
                vals = r.get("values") or {}
                count = next((number(v)[0] for h, v in vals.items() if _ga4_field(h) == "event_count"), None)
                if count is not None:
                    events[str(r["name"]).strip()] = round(count)
            if not events:
                continue
            leads = composer.lead_values({"ga4": {"events": events}})
            if which == "current":
                ga4 = dict(snapshot.get("ga4") or {})
                had = dict(ga4.get("events") or {}) if not complete and len(events) < 3 else {}
                ga4["events"] = dict(sorted({**had, **events}.items(), key=lambda kv: -kv[1]))
                snapshot["ga4"] = ga4
            else:
                previous_values = dict(snapshot.get("previous_values") or {})
                previous_values["leads"] = leads
                snapshot["previous_values"] = previous_values
                _mark_compared(snapshot)
            found = [m["label"] for m in composer.LEAD_KEYS if leads.get(m["key"])]
            filled.append(f"{len(events)} events for {'this' if which == 'current' else 'last'} period")
            if not found:
                notices.append({"level": "info", "text":
                    "None of these events look like an enquiry (a thank-you page, email or phone click, purchase), "
                    "so the lead figures are 0 — type them in below if your site names them differently."})

    if "ga4_sources" in kinds:
        for idx, which in periods.items():
            if which == "previous":
                continue
            merged: dict[str, float] = {}
            for r in _rows_for(table, idx):
                source = str(r["name"]).split(" / ")[0].strip()
                sessions = _ga4_values(r.get("values") or {}).get("sessions")
                if source and sessions is not None:
                    merged[source] = merged.get(source, 0) + sessions
            if merged:
                _put_rows(snapshot, "ga4.traffic_sources",
                          [{"source": k, "sessions": v} for k, v in merged.items()], complete)
                filled.append(f"{len(merged)} traffic sources")

    if corrected:
        notices.append({"level": "warning", "text":
            "Some engaged sessions didn't agree with the screenshot's own sessions × engagement rate, so the "
            f"worked-out figure was used: {'; '.join(corrected)}. Check them against the screenshot."})
    if missing:
        order = [l for _, l, _ in composer._LIST_BY_PATH["ga4.countries_detail"]["columns"]]
        names = sorted(missing, key=lambda l: order.index(l) if l in order else 99)
        notices.append({"level": "info", "text":
            f"Not on the screenshot: {', '.join(names)} (GA4 hides some columns off to the right). They were left "
            "as they were — 0 if nothing was there before. Scroll the table right and upload again, type them in, "
            "or hide those columns in the table below."})
    if rounded:
        notices.append({"level": "warning", "text":
            f"Search Console rounds big totals on screen: {', '.join(sorted(rounded))}. The rounded figure was "
            "filled in — type the exact one if you have it (Export gives it)."})

    slides = [SCREEN_SLIDE[k] for k in kinds if k in SCREEN_SLIDE]
    if slide and slide not in slides:
        notices.insert(0, {"level": "info", "text":
            f"This screenshot is {read.get('screen') or 'a different screen'}, so it filled "
            f"{', '.join(SLIDE_NAME.get(s, s) for s in slides)} rather than {SLIDE_NAME.get(slide, slide)}."})
    if not edits and not filled and notices[dated:]:
        # Read, but nothing it holds has a place: say why rather than "nothing found".
        raise ShotError("Nothing was filled. " + " ".join(n["text"] for n in notices[dated:]))
    if not edits and not filled:
        raise ShotError("The screenshot was read, but no figures could be taken from it. Make sure the table "
                        "or the totals are fully in view — the sample beside the upload button shows how.")
    unique = []
    for n in notices:
        if n not in unique:
            unique.append(n)
    return {"edits": edits, "filled": filled, "notices": unique, "slides": slides,
            "kinds": kinds, "periods": {str(k): v for k, v in periods.items()}}


def _gsc_rows(rows: list[dict], name_key: str) -> list[dict]:
    out = []
    for r in rows:
        got: dict[str, float] = {}
        for header, raw in (r.get("values") or {}).items():
            field = _gsc_field(header)
            v, _ = number(raw)
            if field and v is not None and field not in got:
                got[field] = v
        if "clicks" not in got and "impressions" not in got:
            continue
        row = {name_key: str(r["name"]).strip(), "clicks": got.get("clicks", 0), "impressions": got.get("impressions", 0)}
        if got.get("impressions"):
            row["ctr"] = round(row["clicks"] / row["impressions"] * 100, 2)
        elif "ctr" in got:
            row["ctr"] = got["ctr"]
        if "position" in got:
            row["position"] = got["position"]
        out.append(row)
    return out


def _check_engaged(v: dict[str, float]) -> Optional[str]:
    """Engaged sessions, sessions and engagement rate are on the same row,
    so each can check the others: a digit the AI misread (38 for 30) shows
    up as a rate that does not match. The rate is a separate, short figure
    and so the likelier one to be right; the engaged count is set from it.
    Returns what was changed, for the notice."""
    sessions, engaged, rate = v.get("sessions"), v.get("engaged_sessions"), v.get("engagement_rate")
    if sessions is None or engaged is None or rate is None:
        return None
    expected = sessions * rate
    if abs(engaged - expected) <= max(1.5, expected * 0.03):
        return None
    v["engaged_sessions"] = round(expected)
    return f"read {engaged:g}, used {round(expected)}"


def _ga4_row(v: dict[str, float], country: bool) -> tuple[dict, bool]:
    """A GA4 row as the report stores it: counts and total seconds, the
    rates on screen turned back into the counts they come from. Returns
    whether sessions had to be estimated."""
    guessed = False
    sessions = v.get("sessions")
    engaged = v.get("engaged_sessions")
    users = v.get("active_users") or v.get("total_users")
    rate = v.get("engagement_rate")
    if engaged is None and v.get("eng_per_user") is not None and users:
        engaged = v["eng_per_user"] * users
    if sessions is None and engaged is not None and rate:
        sessions = engaged / rate
    if engaged is None and sessions is not None and rate is not None:
        engaged = sessions * rate
    if sessions is None and country and users is not None:
        # Nobody engaged, so the rate cannot say how many sessions there were;
        # every visitor had at least one.
        sessions = users
        guessed = True
    elif sessions is not None and "sessions" not in v:
        guessed = True
    row: dict[str, float] = {}
    if sessions is not None:
        row["sessions"] = round(sessions)
    if engaged is not None:
        row["engaged_sessions"] = round(engaged)
    if v.get("time_per_session") is not None and sessions:
        row["engagement_seconds"] = round(v["time_per_session"] * sessions)
    elif v.get("time_per_user") is not None and users:
        row["engagement_seconds"] = round(v["time_per_user"] * users)
    if v.get("event_count") is not None:
        row["event_count"] = round(v["event_count"])
    elif v.get("events_per_session") is not None and sessions:
        row["event_count"] = round(v["events_per_session"] * sessions)
    if v.get("key_events") is not None:
        row["key_events"] = round(v["key_events"])
    if country:
        if users is not None:
            row["active_users"] = round(users)
        if v.get("new_users") is not None:
            row["new_users"] = round(v["new_users"])
        if v.get("revenue") is not None:
            row["revenue"] = round(v["revenue"], 2)
    return row, guessed


def _mark_compared(snapshot: dict) -> None:
    period = dict(snapshot.get("period") or {})
    compare = dict(period.get("compare") or {})
    if not compare.get("hasData"):
        compare["hasData"] = True
        period["compare"] = compare
        snapshot["period"] = period
