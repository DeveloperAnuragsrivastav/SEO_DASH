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


def number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "—", "none", "None", "n/a", "NA"):
        return None
    pct = s.endswith("%")
    try:
        n = float(s.rstrip("%"))
    except ValueError:
        raise SheetError(f"“{v}” is not a number.")
    return n / 100 if pct else n


_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%y",
                 "%b'%y", "%b %y", "%b %Y", "%B %Y", "%Y-%m", "%b-%y", "%B-%Y", "%b-%Y")


def parse_day(v: Any) -> Optional[datetime.date]:
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v or "").strip().split("T")[0]
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def month_of_header(header: str) -> Optional[datetime.date]:
    d = parse_day(header)
    return datetime.date(d.year, d.month, 1) if d else None


def truthy(v: Any) -> Optional[bool]:
    s = str(v if v is not None else "").strip().lower()
    if s in ("", "-", "none"):
        return None
    return s in ("yes", "y", "true", "1", "t", "✓", "x")


# ── Readers: sheet → pulled-style rows, for the figures built from daily rows ──

METRIC_SHEETS = {
    "gsc": ("clicks", "impressions", "ctr", "position"),
    "ga4": ("sessions", "users", "engaged_sessions", "conversions", "revenue"),
    "gbp": ("calls", "direction_requests", "website_clicks", "bookings", "chat_clicks",
            "impressions_desktop_maps", "impressions_desktop_search",
            "impressions_mobile_maps", "impressions_mobile_search"),
}


def metric_rows(provider: str, table: list[dict], windows: list[tuple[datetime.date, datetime.date]]) -> list[tuple]:
    """Daily (or monthly) figures as rows the report builder reads, keeping
    only days inside the given windows."""
    keys = METRIC_SHEETS[provider]
    out: list[tuple] = []
    for i, row in enumerate(table, start=2):
        day = parse_day(pick(row, "date", "day", "month"))
        if day is None:
            raise SheetError(f"Row {i}: the date is missing or not a date.")
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
    now_col = next((h for h in headers if month_of_header(h) == month), None)
    prev_col = next((h for h in headers if month_of_header(h) == prev_month), None)
    if now_col is None:
        now_col = next((h for h in headers if norm(h) in ("position", "this_month", "current_rank", "rank")), None)
    if prev_col is None:
        prev_col = next((h for h in headers if norm(h) in ("previous", "last_month", "previous_position")), None)
    if now_col is None and prev_col is None:
        raise SheetError(f"No column for {month:%b'%y} (this month) or {prev_month:%b'%y} (last month).")
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
        sv = number(pick(row, "sv", "search_volume", "volume"))
        init = number(pick(row, "initial_ranking", "initial_rank", "initial"))
        if sv is not None:
            kw["search_volume"] = int(sv)
        if init:
            kw["initial_rank"] = int(init)
        if now_col is not None and number(row.get(now_col)):
            kw["position"] = int(number(row.get(now_col)))
        if prev_col is not None and number(row.get(prev_col)):
            kw["previous_position"] = int(number(row.get(prev_col)))
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
    for row in table:
        prompt = " ".join(str(pick(row, "prompt", "prompts") or "").split())
        if not prompt:
            continue
        m = pick(row, "month", "date")
        d = parse_day(m) if m not in (None, "") else None
        if d and datetime.date(d.year, d.month, 1) != month:
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
    """Month, Activity Name, URL, Count — this month's rows replace the list."""
    from urllib.parse import urlparse
    links = []
    for i, row in enumerate(table):
        m = pick(row, "month", "date")
        if m not in (None, ""):
            d = parse_day(m)
            if d and datetime.date(d.year, d.month, 1) != month:
                continue
        kind = str(pick(row, "activity_name", "activity_type", "activity", "type") or "").strip()
        url = str(pick(row, "url", "link") or "").strip()
        if not kind and not url:
            continue
        count = number(pick(row, "count", "links")) or 1
        links.append({"id": f"u{i}", "activity_type": kind or "Link", "url": url or None,
                      "domain": urlparse(url).netloc.replace("www.", "") if url else None, "count": int(count)})
    if not links:
        raise SheetError(f"No rows for {month:%B %Y} in this sheet.")
    snapshot["links"] = links
    return len(links)


def apply_work(snapshot: dict, table: list[dict]) -> int:
    """Activity Type, Count, Notes — replaces this month's work list."""
    acts = []
    for row in table:
        kind = str(pick(row, "activity_type", "activity", "task", "type") or "").strip()
        if not kind:
            continue
        notes = str(pick(row, "notes", "note", "details") or "").strip() or None
        acts.append({"activity_type": kind, "count": int(number(pick(row, "count")) or 1), "notes": notes})
    if not acts:
        raise SheetError("No tasks found — the sheet needs an Activity Type column.")
    snapshot["activities"] = acts
    return len(acts)
