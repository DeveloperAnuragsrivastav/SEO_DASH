"""Sheets uploaded in the report builder, read straight into the draft.

An upload changes only the report being built — nothing is recorded for the
client until the report is published. Each reader takes the layout the
builder's sample sheet shows, in CSV or Excel.
"""
from __future__ import annotations

import csv
import datetime
import io
import re
import uuid
from typing import Any, Optional

MAX_SHEET_BYTES = 2 * 1024 * 1024


class SheetError(ValueError):
    """A sheet that cannot be read; the message is shown to the person."""


def read_table(filename: str, content: bytes) -> list[dict[str, Any]]:
    """Rows of a CSV or Excel sheet, keyed by header — lower case, spaces as
    underscores — with the original header kept under the same key."""
    if len(content) > MAX_SHEET_BYTES:
        raise SheetError("The sheet must be 2 MB or smaller.")
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        import openpyxl
        try:
            ws = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True).active
        except Exception:
            raise SheetError("That Excel file could not be opened.")
        it = ws.iter_rows(values_only=True)
        header = next(it, None)
        raw = [list(r) for r in it]
    elif name.endswith(".csv") or not name:
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        raw = list(reader)
    else:
        raise SheetError("Upload a .csv or .xlsx file.")
    if not header:
        raise SheetError("The sheet is empty.")
    keys = [str(h or "").strip() for h in header]
    rows = []
    for values in raw:
        if not any(str(v or "").strip() for v in values):
            continue
        rows.append({k: v for k, v in zip(keys, values) if k})
    if not rows:
        raise SheetError("The sheet has a header but no rows.")
    return rows


def norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key or "").strip().lower()).strip("_")


def pick(row: dict, *names: str) -> Any:
    wanted = {norm(n) for n in names}
    for k, v in row.items():
        if norm(k) in wanted:
            return v
    return None


# Cells that mean "no figure" — left empty rather than read as 0 or refused.
_BLANK = {"", "-", "--", "—", "–", "_", "?", ".", "none", "null", "nil", "nan", "n/a", "na", "n.a.", "n.a",
          "#n/a", "#na", "#value!", "#ref!", "#div/0!", "not available", "no data", "tbd", "blank"}
# A position that means "not in the top 100".
_NOT_RANKED = {"nr", "n/r", "not ranked", "unranked", "not ranking", "not found", "100+", ">100", "> 100",
               "101+", "out", "-1", "0"}
_SCALE = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "l": 100_000, "lakh": 100_000, "cr": 10_000_000}


def is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in _BLANK)


def number(v: Any) -> Optional[float]:
    """A figure as people type it: 1,234 · 1 234 · ₹1,200 · $4.5k · 12% · 2.3L ·
    (blank, -, N/A, null…) → None. 0 stays 0. Anything else is refused with
    the cell's own text, so the person can find it."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)          # NaN from Excel
    s = str(v).strip()
    if s.lower() in _BLANK:
        return None
    s = re.sub(r"[\s,₹$€£¥]|rs\.?|inr|usd", "", s, flags=re.I)
    s = s.replace("\u2212", "-")                    # the typographic minus
    pct = s.endswith("%")
    s = s.rstrip("%")
    m = re.fullmatch(r"([+-]?\d*\.?\d+)(k|m|b|l|lakh|cr)?", s, flags=re.I)
    if not m:
        raise SheetError(f"“{v}” is not a number.")
    n = round(float(m.group(1)) * _SCALE.get((m.group(2) or "").lower(), 1), 6)
    return round(n / 100, 8) if pct else n


def position(v: Any) -> Optional[int]:
    """A ranking position: 1–100, or None for blank / not ranked / 100+."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in _NOT_RANKED | _BLANK:
        return None
    n = number(v)
    if n is None or n < 1:
        return None
    return int(round(n)) if n <= 100 else None


_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%y",
                 "%b'%y", "%b %y", "%b %Y", "%B %Y", "%Y-%m", "%b-%y", "%B-%Y", "%b-%Y")


def parse_day(v: Any) -> Optional[datetime.date]:
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v or "").strip().split("T")[0].split(" 00:00")[0]
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def month_of_header(header: Any, year_hint: Optional[int] = None) -> Optional[datetime.date]:
    """The month a column heading or Month cell names, written any usual way:
    Sep'26, Sep’26, Sept 2026, September, 09/2026, 2026-09, Sep-26, 2026-09-15,
    or a period such as "5 Sep – 4 Oct" (read as the month it starts in).
    A month with no year takes `year_hint`."""
    if isinstance(header, (datetime.date, datetime.datetime)):
        d = header.date() if isinstance(header, datetime.datetime) else header
        return datetime.date(d.year, d.month, 1)
    text = str(header or "").strip().lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    if not text:
        return None
    d = parse_day(text)
    if d:
        return datetime.date(d.year, d.month, 1)
    m = re.search(r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[\s'\-/,]*(\d{4}|\d{2})?(?!\d)", text)
    if m:
        year = m.group(2)
        y = (2000 + int(year) if len(year) == 2 else int(year)) if year else year_hint
        return datetime.date(y, _MONTHS[m.group(1)], 1) if y else None
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{4})|(\d{4})[/\-.](\d{1,2})", text)
    if m:
        mo, y = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(4)), int(m.group(3)))
        return datetime.date(y, mo, 1) if 1 <= mo <= 12 else None
    return None


_THIS = ("this_month", "this_period", "current", "current_month", "current_period", "now", "latest",
         "position", "current_rank", "current_position", "rank", "value", "this_cycle")
_LAST = ("last_month", "previous", "previous_month", "prev", "last_period", "previous_period",
         "previous_position", "last_rank", "before")


def period_columns(headers: list[str], month: datetime.date, prev_month: datetime.date) -> tuple[Optional[str], Optional[str], str]:
    """Which columns hold this period's and last period's figures.

    In order: a heading naming this report's month (any spelling); a heading
    such as "This month" / "Previous"; failing both, the latest month the sheet
    has, with the one before it as last period. Returns the two headings (either
    may be None) and how they were chosen, to tell the person."""
    dated = {h: month_of_header(h, month.year) for h in headers}
    now = next((h for h, m in dated.items() if m == month), None)
    prev = next((h for h, m in dated.items() if m == prev_month), None)
    if now is None:
        now = next((h for h in headers if norm(h) in _THIS), None)
    if prev is None:
        prev = next((h for h in headers if norm(h) in _LAST), None)
    if now is None and prev is None:
        months = sorted((m, h) for h, m in dated.items() if m)
        if months:
            now = months[-1][1]
            prev = months[-2][1] if len(months) > 1 else None
            return now, prev, f"read “{now}” as this period" + (f" and “{prev}” as the one before" if prev else "")
    return now, prev, ""


def rows_for_month(table: list[dict], month: datetime.date) -> tuple[list[dict], str]:
    """The rows of a sheet with a Month (or Date) column that belong to this
    report's month. Rows without a month count. If the sheet's months are all
    different from this one, its latest month is used — and said."""
    tagged = []
    for row in table:
        m = pick(row, "month", "date", "period")
        tagged.append((None if is_blank(m) else month_of_header(m, month.year), row))
    months = {m for m, _ in tagged if m}
    if not months or month in months:
        return [r for m, r in tagged if m is None or m == month], ""
    latest = max(months)
    return [r for m, r in tagged if m is None or m == latest], f"used the rows for {latest:%b %Y}, the latest month in the sheet"


def truthy(v: Any) -> Optional[bool]:
    """Yes/No as people mark it; blank or unknown → None (not checked)."""
    s = str(v if v is not None else "").strip().lower()
    if s in _BLANK:
        return None
    if s in ("yes", "y", "true", "1", "t", "✓", "✔", "x", "mentioned", "cited", "found", "present", "haan", "ha"):
        return True
    if s in ("no", "n", "false", "0", "f", "✗", "✘", "not mentioned", "absent", "not found", "nahi"):
        return False
    return None


# ── Readers: sheet → pulled-style rows, for the figures built from daily rows ──

METRIC_SHEETS = {
    "gsc": ("clicks", "impressions", "ctr", "position"),
    "ga4": ("sessions", "users", "engaged_sessions", "conversions", "revenue"),
    "gbp": ("calls", "direction_requests", "website_clicks", "bookings", "chat_clicks",
            "impressions_desktop_maps", "impressions_desktop_search",
            "impressions_mobile_maps", "impressions_mobile_search"),
}


def metric_rows(provider: str, table: list[dict], windows: list[tuple[datetime.date, datetime.date]],
                month_rows: Optional[dict] = None) -> list[tuple]:
    """Daily (or monthly) figures as rows the report builder reads, keeping
    only days inside the given windows. A row dated by its month alone
    ("Sep'26", "2026-09") stands for the whole period filed under that month
    (`month_rows`: month → window), whatever day that period starts on."""
    keys = METRIC_SHEETS[provider]
    month_rows = month_rows or {}
    out: list[tuple] = []
    for i, row in enumerate(table, start=2):
        raw = pick(row, "date", "day", "month", "period")
        if is_blank(raw):
            continue                                   # a spacer or totals row
        day = parse_day(raw)
        whole_month = None
        if day is None or (isinstance(raw, str) and not re.search(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}", raw)):
            whole_month = month_of_header(raw, (windows[0][1] if windows else datetime.date.today()).year)
        if whole_month is not None and whole_month in month_rows:
            day = month_rows[whole_month][1]           # counted inside that period
        elif day is None:
            raise SheetError(f"Row {i}: “{raw}” is not a date or a month.")
        if not any(lo <= day <= hi for lo, hi in windows):
            continue
        for key in keys:
            v = number(pick(row, key, key.replace("_", " ")))
            if v is None:
                continue
            if provider == "gsc" and key == "ctr" and v > 1:
                v = v / 100
            out.append((provider, day, key, None, None, v, "manual"))
    return out


# ── Readers that change the draft's own lists ───────────────────────────────

def apply_rankings(snapshot: dict, table: list[dict], month: datetime.date, prev_month: datetime.date) -> int:
    """Keyword, SV, Initial Ranking and a column per month. This month's and
    last month's columns fill the two positions; any keyword not yet in the
    report is added to it."""
    from app.services.report_composer import ranking_summary
    rankings = dict(snapshot.get("rankings") or {})
    keywords = [dict(k) for k in rankings.get("keywords") or []]
    by_term = {str(k.get("term") or "").strip().lower(): k for k in keywords}
    headers = list(table[0].keys())
    now_col, prev_col, how = period_columns(headers, month, prev_month)
    if now_col is None and prev_col is None:
        raise SheetError(f"No position column found — name one {month:%b'%y} (or “This month”), "
                         f"and last period's {prev_month:%b'%y} (or “Previous”).")
    snapshot.setdefault("_upload_note", how)
    done = 0
    for row in table:
        term = " ".join(str(pick(row, "keyword", "term") or "").split())
        if not term:
            continue
        kw = by_term.get(term.lower())
        if kw is None:
            kw = {"keyword_id": f"new-{uuid.uuid4().hex[:12]}", "term": term, "history": {}, "change": None,
                  "position": None, "previous_position": None, "initial_rank": None, "search_volume": None}
            keywords.append(kw)
            by_term[term.lower()] = kw
        sv = number(pick(row, "sv", "search_volume", "volume", "monthly_searches"))
        init = position(pick(row, "initial_ranking", "initial_rank", "initial", "starting_rank", "start"))
        if sv is not None:
            kw["search_volume"] = int(sv)
        if init:
            kw["initial_rank"] = init
        # A blank cell leaves the figure as it was; "NR" / 100+ / 0 means not
        # in the top 100 and clears it.
        if now_col is not None and not is_blank(row.get(now_col)):
            kw["position"] = position(row.get(now_col))
        if prev_col is not None and not is_blank(row.get(prev_col)):
            kw["previous_position"] = position(row.get(prev_col))
        if kw.get("initial_rank") and kw.get("position"):
            kw["change"] = kw["initial_rank"] - kw["position"]
        done += 1
    rankings["keywords"] = keywords
    rankings["summary"] = ranking_summary(keywords, rankings.get("summary_overrides"))
    snapshot["rankings"] = rankings
    return done


ASSISTANT_COLUMNS = {
    "chatgpt": "chatgpt", "gpt": "chatgpt", "claude": "claude", "gemini": "gemini", "google_gemini": "gemini",
    "perplexity": "perplexity", "grok": "grok", "ai_overview": "google_ai_overview",
    "google_ai_overview": "google_ai_overview", "ai_overviews": "google_ai_overview",
}


def apply_ai(snapshot: dict, table: list[dict], month: datetime.date) -> int:
    """Prompts with Yes/No per assistant, for this month (a Month column, when
    there is one, picks this month's rows)."""
    headers = list(table[0].keys())
    engines = {h: ASSISTANT_COLUMNS[norm(h)] for h in headers if norm(h) in ASSISTANT_COLUMNS}
    if not engines:
        raise SheetError("No assistant columns found — use ChatGPT, AI Overview, Gemini, Perplexity or Claude.")
    rows = [{k: v for k, v in r.items() if k != "unchecked"} for r in snapshot.get("ai_visibility") or []]
    ids = {str(r.get("prompt") or "").strip().lower(): r.get("prompt_id") for r in rows}
    done = 0
    rows_now, how = rows_for_month(table, month)
    snapshot.setdefault("_upload_note", how)
    for row in rows_now:
        prompt = " ".join(str(pick(row, "prompt", "prompts", "query", "question") or "").split())
        if not prompt:
            continue
        pid = ids.get(prompt.lower()) or f"new-{uuid.uuid4().hex[:12]}"
        ids[prompt.lower()] = pid
        for header, platform in engines.items():
            seen = truthy(row.get(header))
            if seen is None:
                continue
            rows = [r for r in rows if not (str(r.get("prompt_id")) == str(pid) and r.get("platform") == platform)]
            rows.append({"prompt_id": pid, "prompt": prompt, "platform": platform, "mentioned": seen, "cited_pages": None})
        done += 1
    snapshot["ai_visibility"] = rows
    return done


def apply_links(snapshot: dict, table: list[dict], month: datetime.date) -> int:
    """Month, Activity Name, URL — one row per link; this month's rows replace
    the list. A Count column, if a sheet still has one, is read too."""
    from urllib.parse import urlparse
    links = []
    rows_now, how = rows_for_month(table, month)
    snapshot.setdefault("_upload_note", how)
    for i, row in enumerate(rows_now):
        kind = str(pick(row, "activity_name", "activity_type", "activity", "type") or "").strip()
        url = str(pick(row, "url", "link") or "").strip()
        if not kind and not url:
            continue
        count = number(pick(row, "count", "links")) or 1
        links.append({"id": f"u{i}", "activity_type": kind or "Link", "url": url or None,
                      "domain": urlparse(url).netloc.replace("www.", "") if url else None, "count": int(count)})
    if not links:
        raise SheetError("No links found — the sheet needs an Activity or URL column.")
    snapshot["links"] = links
    return len(links)


def apply_work(snapshot: dict, table: list[dict]) -> int:
    """Activity Type, Notes — one row per task, replacing this month's work
    list. Rows naming the same task are added up ("Blog post" on five rows is
    Blog post ×5). A Count column, if a sheet still has one, is read too."""
    acts: dict[str, dict] = {}
    for row in table:
        kind = " ".join(str(pick(row, "activity_type", "activity", "task", "type", "activity_name", "work") or "").split())
        if not kind:
            continue
        note = str(pick(row, "notes", "note", "details", "description") or "").strip()
        given = number(pick(row, "count", "qty", "quantity"))
        a = acts.setdefault(kind.lower(), {"activity_type": kind, "count": 0, "notes": []})
        a["count"] += int(given) if given and given > 0 else 1
        if note and not is_blank(note) and note not in a["notes"]:
            a["notes"].append(note)
    if not acts:
        raise SheetError("No tasks found — the sheet needs an Activity Type column.")
    snapshot["activities"] = [{"activity_type": a["activity_type"], "count": a["count"],
                               "notes": "; ".join(a["notes"])[:300] or None} for a in acts.values()]
    return sum(a["count"] for a in acts.values())
