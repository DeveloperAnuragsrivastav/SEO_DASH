from __future__ import annotations
"""Every fixed string the report prints, in one place.

Before this, a card's name lived in `slide_deck.py`, a column header lived in
the template, and a commentary label lived in a macro call — so changing the
words a client reads meant editing code, and nothing in the builder could
reach them. Each string below has an id; the template and the deck both ask
for it by id, and the builder writes overrides against the same ids.

`block` is the commentary block the string belongs to, which is what groups it
in the builder. `basics` covers the cover and the closing slide.
"""

from typing import Any, Callable

TEXT_MAX = 160

# key, block, what it is (shown in the builder), the wording used when unedited
TEXTS: list[tuple[str, str, str, str]] = [
    # ── Cover and closing ──────────────────────────────────────────────────
    ("cover.period_label", "basics", "Cover — period label", "Reporting period"),
    # {period} is the report month ("September 2026"); {range} the exact dates.
    ("cover.tags", "basics", "Cover — service tags (separate with |)", "SEO | Content | AI visibility | Growth"),
    ("cover.period", "basics", "Cover — period shown ({period} = month, {range} = exact dates)", "{period}"),
    ("baseline.note", "basics", "First report — explanatory note",
     "This is the first report for this client, so there is no earlier period to measure "
     "against yet. The figures below are the starting point every following month is "
     "compared with."),
    ("closing.note", "basics", "Closing — sign-off",
     "Share any feedback on this report and we’ll set next month’s targets together."),

    # ── Performance Highlight ──────────────────────────────────────────────
    ("kpi.keywords.name", "key_metrics", "Figure — keywords on page one", "Keywords on page 1"),
    ("kpi.keywords.note", "key_metrics", "Figure — keywords, small print", "in Google\u2019s top 10"),
    ("kpi.clicks.name", "key_metrics", "Figure — search clicks", "Clicks from search"),
    ("kpi.impressions.name", "key_metrics", "Figure — search impressions", "Search impressions"),
    ("kpi.sessions.name", "key_metrics", "Figure — website traffic", "Website sessions"),
    ("kpi.leads.name", "key_metrics", "Figure — leads", "Leads"),
    ("kpi.leads.note", "key_metrics", "Figure — leads, small print", "enquiries recorded"),
    ("kpi.revenue.name", "key_metrics", "Figure — revenue", "Revenue"),
    ("kpi.ai.name", "key_metrics", "Figure — AI visibility", "AI visibility"),
    ("kpi.ai.note", "key_metrics", "Figure — AI visibility, small print", "of AI answers name you"),
    ("kpi.ai_traffic.name", "key_metrics", "Figure — AI assistant traffic", "AI assistant traffic"),
    ("kpi.ai_traffic.note", "key_metrics", "Figure — AI traffic, small print", "visits sent by AI answers"),
    ("kpi.gbp.name", "key_metrics", "Figure — profile interactions", "Profile interactions"),
    ("tag.baseline", "key_metrics", "Badge — no earlier period", "Baseline"),
    ("tag.tracked", "key_metrics", "Badge — tracked figure", "Tracked"),
    ("tag.ai", "key_metrics", "Badge — AI search figure", "AI search"),
    ("tag.this_period", "key_metrics", "Badge — this period only", "This period"),
    ("verdict.key_metrics", "key_metrics", "Commentary heading", "The verdict"),

    # ── Leads & Conversion ─────────────────────────────────────────────────
    ("lead.thank_you", "leads", "Figure — thank-you page", "Thank-you page"),
    ("lead.email", "leads", "Figure — email clicks", "Email clicks"),
    ("lead.phone", "leads", "Figure — phone number clicks", "Phone number clicks"),
    ("lead.transactions", "leads", "Figure — transactions", "Transactions"),
    ("lead.revenue", "leads", "Figure — revenue", "Revenue"),
    ("leads.other.name", "leads", "Card — other events", "Other conversion events recorded"),
    ("leads.other.sub", "leads", "Card — other events, sub-line",
     "Named as they are set up in this property’s Analytics"),
    ("verdict.leads", "leads", "Commentary heading", "What the enquiries say"),

    # ── Ranking Summary ────────────────────────────────────────────────────
    ("rank.band_col", "rankings", "Table — first column", "Position band"),
    ("rank.chart.name", "rankings", "Chart — title", "Ranking distribution over time"),
    ("rank.chart.sub", "rankings", "Chart — sub-line", "Tracked terms in each band, from the start to now"),
    ("rank.initial", "rankings", "Column — the starting point", "Initial"),
    ("band.top10", "rankings", "Band — first page", "Top 10"),
    ("band.11_20", "rankings", "Band — 11 to 20", "11 – 20"),
    ("band.21_30", "rankings", "Band — 21 to 30", "21 – 30"),
    ("band.31_40", "rankings", "Band — 31 to 40", "31 – 40"),
    ("band.41_50", "rankings", "Band — 41 to 50", "41 – 50"),
    ("band.51_100", "rankings", "Band — 51 to 100", "51 – 100"),
    ("band.none", "rankings", "Band — unranked", "Not in Top 100"),
    ("verdict.rankings", "rankings", "Commentary heading", "Takeaway"),

    # ── Keywords Rankings Tracking ─────────────────────────────────────────
    ("kw.term_col", "rankings_table", "Table — keyword column", "Keyword"),
    ("kw.new", "rankings_table", "Movement — first appearance", "New entry"),
    ("kw.note", "rankings_table", "Small print under the table",
     "“—” indicates the term was not in search results that month."),

    # ── Traffic Progress Summary ───────────────────────────────────────────
    ("ga4.sessions", "ga4", "Figure — sessions", "Sessions"),
    ("ga4.engaged", "ga4", "Figure — engaged sessions", "Engaged sessions"),
    ("ga4.conversions", "ga4", "Figure — conversions", "Conversions"),
    ("ga4.revenue", "ga4", "Figure — revenue", "Revenue"),
    ("verdict.ga4", "ga4", "Commentary heading", "Reading the traffic"),

    # ── Where the traffic came from ────────────────────────────────────────
    ("src.share_col", "ga4_countries", "Column — share", "Share of visits"),

    # ── Traffic (Geographical Distribution) ────────────────────────────────
    ("geo.name", "ga4_countries", "Card — title", "Top countries"),
    ("geo.sub", "ga4_countries", "Card — sub-line", "Sessions and the people behind them"),
    ("verdict.ga4_countries", "ga4_countries", "Commentary heading", "Who is finding you"),

    # ── Click & Impressions ────────────────────────────────────────────────
    ("gsc.clicks", "gsc", "Figure — clicks", "Clicks from Google search"),
    ("gsc.impressions", "gsc", "Figure — impressions", "Times the site was shown"),
    ("gsc.ctr", "gsc", "Figure — click-through rate", "Click-through rate"),
    ("gsc.position", "gsc", "Figure — average position", "Average position"),
    ("verdict.gsc", "gsc", "Commentary heading", "Reading the search numbers"),

    # ── Top Performing Pages ───────────────────────────────────────────────
    ("pages.new", "gsc_pages", "Movement — first appearance", "New"),
    ("pages.held", "gsc_pages", "Movement — unchanged", "Held"),
    ("verdict.gsc_pages", "gsc_pages", "Commentary heading", "Which pages are working"),

    # ── AI Keyword Visibility ──────────────────────────────────────────────
    ("ai.prompt_col", "ai_visibility", "Table — prompt column", "Prompt"),
    ("ai.yes", "ai_visibility", "Result — brand named", "Visible"),
    ("ai.no", "ai_visibility", "Result — brand not named", "Not visible"),
    ("verdict.ai_visibility", "ai_visibility", "Commentary heading", "What the AI results tell us"),

    # ── AI Assistant Referral Traffic ──────────────────────────────────────
    ("airef.name", "ai_referral", "Figure — visits", "Visits referred by an AI assistant"),
    ("airef.split.name", "ai_referral", "Card — per assistant", "Which assistant sent them"),
    ("airef.split.sub", "ai_referral", "Card — per assistant, sub-line", "Sessions by referring assistant"),
    ("verdict.ai_referral", "ai_referral", "Commentary heading", "What the assistants are sending"),

    # ── Google Business Profile Performance ────────────────────────────────
    ("gbp.total.name", "gbp", "Figure — interactions", "Business Profile interactions"),
    ("gbp.total.sub", "gbp", "Figure — interactions, sub-line",
     "Calls, chats, direction requests, bookings and website clicks generated directly from the listing."),
    ("gbp.calls", "gbp", "Action — calls", "Calls"),
    ("gbp.chat", "gbp", "Action — chat clicks", "Chat clicks"),
    ("gbp.website", "gbp", "Action — website clicks", "Website clicks"),
    ("gbp.directions", "gbp", "Action — direction requests", "Direction requests"),
    ("gbp.bookings", "gbp", "Action — bookings", "Bookings"),
    ("verdict.gbp", "gbp", "Commentary heading", "Reading the profile"),

    # ── How people found the profile ───────────────────────────────────────

    # ── Authority Building Through Backlinks ───────────────────────────────
    ("links.total", "links", "Figure — links built", "Links built"),
    ("links.domains", "links", "Figure — unique domains", "Unique domains"),
    ("links.kinds", "links", "Figure — activity types", "Activity types"),
    ("links.chart.name", "links", "Card — per type", "By activity type"),
    ("links.chart.sub", "links", "Card — per type, sub-line", "Links built in each category"),
    ("verdict.links", "links", "Commentary heading", "What the links are worth"),

    # ── Work Done & Proof ──────────────────────────────────────────────────
    ("verdict.work", "work", "Commentary heading", "Carrying forward:"),

    # ── Next Plan of Action ────────────────────────────────────────────────
    ("plan.now", "plan", "Lane — this coming month", "Now · next 30 days"),
    ("plan.next", "plan", "Lane — the month after", "Next · 60 – 90 days"),
]

TEXT_DEFAULTS: dict[str, str] = {k: d for k, _b, _l, d in TEXTS}
TEXT_BLOCK: dict[str, str] = {k: b for k, b, _l, _d in TEXTS}

# The builder shows these grouped under the block they belong to.
TEXT_FIELDS: list[dict[str, str]] = [
    {"key": k, "block": b, "label": l, "default": d} for k, b, l, d in TEXTS
]


def current_texts(snapshot: dict) -> dict[str, str]:
    """The stored overrides only — anything absent means "use the default"."""
    stored = (snapshot or {}).get("copy")
    stored = stored.get("texts") if isinstance(stored, dict) else None
    if not isinstance(stored, dict):
        return {}
    return {
        k: str(v).strip()[:TEXT_MAX]
        for k, v in stored.items()
        if k in TEXT_DEFAULTS and str(v or "").strip()
    }


def merge_texts(current: dict[str, str], incoming: Any) -> dict[str, str]:
    """Apply an edit. A blank value clears that override; unknown ids are ignored."""
    out = dict(current or {})
    if not isinstance(incoming, dict):
        return out
    for key, value in incoming.items():
        if key not in TEXT_DEFAULTS:
            continue
        text_ = str(value or "").strip()[:TEXT_MAX]
        if text_:
            out[key] = text_
        else:
            out.pop(key, None)
    return out


def resolver(copy: dict | None) -> Callable[..., str]:
    """`t('some.key')` — the override if one was written, else the default.

    Unknown ids return empty rather than raising: a template typo should print
    nothing visible, not fail a client's report at render time.
    """
    stored = copy.get("texts") if isinstance(copy, dict) else None
    stored = stored if isinstance(stored, dict) else {}

    def t(key: str, **tokens: str) -> str:
        value = str(stored.get(key) or "").strip() or TEXT_DEFAULTS.get(key, "")
        for token, replacement in tokens.items():
            value = value.replace("{" + token + "}", str(replacement))
        return value

    return t
