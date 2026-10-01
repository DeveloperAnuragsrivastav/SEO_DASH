from __future__ import annotations
"""PDF generation service — renders a Jinja2 HTML template with Playwright/Chromium."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# Template directory (relative to this file)
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)

# Custom Jinja2 filter to format numbers with commas
def _fmt_filter(value):
    """A figure as a client reads it: whole, with thousand separators.

    Everything this filter touches is a count — clicks, sessions, calls,
    links. Summing or averaging them across months leaves decimals that mean
    nothing to a reader; "721.82 calls" is not a number anyone made. Figures
    that genuinely carry decimals (average position, CTR) are rounded
    explicitly at the point of use instead.
    """
    try:
        return f"{int(round(float(value or 0))):,}"
    except (ValueError, TypeError):
        return str(value)

_jinja_env.filters["fmt"] = _fmt_filter


def _pages(items, most: int):
    """A list split over as few slides as it needs, `most` to a slide at the
    most, the rows shared out evenly — 30 keywords print 15 and 15, never 24
    and a stranded 6. An empty list is one empty page, so its slide still prints."""
    items = list(items or [])
    if not items:
        return [[]]
    count = -(-len(items) // most)
    size = -(-len(items) // count)
    return [items[i:i + size] for i in range(0, len(items), size)]


def _density(n: int, normal: int, compact: int) -> str:
    """How tightly a slide sets its rows: roomy up to `normal`, compact up to
    `compact`, dense past it — so a full slide never overflows the page."""
    return "" if n <= normal else ("d1" if n <= compact else "d2")


_jinja_env.filters["pages"] = _pages
_jinja_env.globals["density"] = _density


def _prepare_template_context(report: dict, client: dict, base_url: str) -> dict:
    """Transform raw report data into the flat context the Jinja2 template expects."""
    snap = report.get("snapshot") or {}
    gsc = snap.get("gsc") or {}
    ga4 = snap.get("ga4") or {}
    gbp = snap.get("gbp") or {}
    rankings = snap.get("rankings") or {"summary": {}, "keywords": []}
    ai_vis = snap.get("ai_visibility") or []
    links = snap.get("links") or []
    activities = snap.get("activities") or []
    screenshots = snap.get("screenshots") or []
    deltas = snap.get("kpi_deltas") or {"gsc": {}, "ga4": {}, "gbp": {}}

    # AI visibility aggregates
    ai_mentioned = sum(1 for m in ai_vis if m.get("mentioned"))
    ai_total = len(ai_vis)
    ai_platforms = len(set(m.get("platform", "") for m in ai_vis))

    # AI by platform breakdown
    ai_by_platform: dict = {}
    for m in ai_vis:
        p = m.get("platform", "unknown")
        if p not in ai_by_platform:
            ai_by_platform[p] = {"mentioned": 0, "total": 0}
        ai_by_platform[p]["total"] += 1
        if m.get("mentioned"):
            ai_by_platform[p]["mentioned"] += 1

    # Link aggregates
    unique_domains = len(set(l.get("domain", "") for l in links))
    link_types: dict = {}
    for l in links:
        t = l.get("activity_type", "Other")
        link_types[t] = link_types.get(t, 0) + int(l.get("count") or 1)

    # Date Range Label
    start_date = report.get("start_date")
    end_date = report.get("end_date")
    
    if start_date and end_date:
        if isinstance(start_date, str):
            from datetime import date
            start_date = date.fromisoformat(start_date)
            end_date = date.fromisoformat(end_date)
            
        month_label = end_date.strftime('%B %Y')
    else:
        month_label = "Unknown Range"

    generated_at = ""
    if report.get("generated_at"):
        from datetime import datetime
        try:
            if isinstance(report["generated_at"], str):
                dt = datetime.fromisoformat(report["generated_at"])
            else:
                dt = report["generated_at"]
            generated_at = dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            generated_at = str(report["generated_at"])

    return {
        "client_name": client.get("name", "Client"),
        "client_domain": client.get("domain", ""),
        "client_logo_url": client.get("logo_url"),
        "client_theme_color": client.get("theme_color"),
        "month_label": month_label,
        "status": str(report.get("status", "draft")).replace("ReportStatus.", ""),
        "generated_at": generated_at,
        "narrative": report.get("narrative"),
        "gsc": gsc,
        "ga4": ga4,
        "gbp": gbp,
        "gsc_top_pages": gsc.get("top_pages", []),
        "gsc_top_queries": gsc.get("top_queries", []),
        "gsc_devices": gsc.get("devices", []),
        "ga4_traffic_sources": ga4.get("traffic_sources", []),
        "ga4_top_pages": ga4.get("top_pages", []),
        "ga4_devices": ga4.get("devices", []),
        "ga4_countries": ga4.get("countries", []),
        "rankings": rankings,
        "keywords": rankings.get("keywords") or [],
        "deltas": deltas,
        "ai_visibility": ai_vis,
        "ai_mentioned": ai_mentioned,
        "ai_total": ai_total,
        "ai_platforms": ai_platforms,
        "ai_by_platform": ai_by_platform,
        "links": links,
        "unique_domains": unique_domains,
        "link_types": link_types,
        "activities": activities,
        "screenshots": screenshots,
        "base_url": base_url,
    }


def render_report_html(comparative_data: dict, client: dict, base_url: str) -> str:
    """Render the comparative report Jinja2 template to an HTML string."""
    template = _jinja_env.get_template("report_slides.html")
    from datetime import datetime
    
    months = comparative_data.get("months", [])
    display_label = months[0] if len(months) == 1 else f"{months[0]} \u2013 {months[-1]}" if months else "Unknown Range"
        
    import base64
    from pathlib import Path
    
    # Convert agency_logo to base64
    agency_logo_b64 = ""
    try:
        from pathlib import Path
        logo_path = Path(__file__).resolve().parent.parent / "static" / "agency_logo.png"
        if logo_path.exists():
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                agency_logo_b64 = f"data:image/png;base64,{encoded_string}"
    except Exception:
        pass

    # Which sections this report shows, and which individual figures within
    # them. Absent selection = show everything.
    from app.services import report_composer as composer

    included = comparative_data.get("included_sections")
    if not isinstance(included, dict):
        included = {}
    sections = {k: bool(included.get(k, True)) for k in composer.SECTION_KEYS}
    # The template still asks about "traffic" for the shared page chrome.
    sections["traffic"] = sections["gsc"] or sections["ga4"] or sections["gbp"]

    chosen_items = comparative_data.get("included_items")
    if not isinstance(chosen_items, dict):
        chosen_items = {}

    def metric_on(item_id: str) -> bool:
        """A figure shows only if its own tick AND its section are on."""
        section = item_id.split(".", 1)[0]
        if section in sections and not sections[section]:
            return False
        return chosen_items.get(item_id, True) is not False

    # Editable headings and brand line. Tokens let an override still carry
    # live values, e.g. "{period} results for {client}".
    copy = comparative_data.get("copy") if isinstance(comparative_data.get("copy"), dict) else {}
    tokens = {"{period}": display_label, "{client}": client.get("name", "") or ""}

    def heading(key: str) -> str:
        return composer.copy_text(copy, key, "title", tokens)

    def subheading(key: str) -> str:
        return composer.copy_text(copy, key, "subtitle", tokens)

    def eyebrow(key: str) -> str:
        return composer.copy_text(copy, key, "eyebrow", tokens)

    from app.config import settings
    from app.services import report_text, slide_deck

    # Every fixed string the report prints, with the agency's own overrides
    # applied. Both the deck and the template resolve through this one call so
    # a card's name cannot differ between where it is built and where it prints.
    t = report_text.resolver(copy)

    period = comparative_data.get("period") or {}
    deck = slide_deck.build(
        comparative_data, client, sections, metric_on,
        display_label, period.get("range") or display_label, t,
    )

    return template.render(
        **deck,
        agency_name=settings.AGENCY_NAME,
        agency_tagline=settings.AGENCY_TAGLINE,
        agency_email=settings.AGENCY_CONTACT_EMAIL,
        agency_contact_line=settings.AGENCY_CONTACT_LINE,
        sections=sections,
        mo=metric_on,
        ct=heading,
        cs=subheading,
        ce=eyebrow,
        t=t,
        brand_line=composer.brand_line(copy),
        cover_screenshot=comparative_data.get("cover_screenshot"),
        nar=lambda key: str((comparative_data.get("narration") or {}).get(key) or "").strip(),
        # A slide switched off in the builder is left out of the report.
        shown=lambda key: key not in set(comparative_data.get("hidden_slides") or []),
        period_rows=comparative_data.get("periods") or [],
        comparative_data=comparative_data,
        months=comparative_data.get("months", []),
        gsc=comparative_data.get("gsc", {}),
        ga4=comparative_data.get("ga4", {}),
        gbp=comparative_data.get("gbp", {}),
        gsc_top_pages=comparative_data.get("gsc", {}).get("top_pages", []),
        gsc_trending=comparative_data.get("gsc", {}).get("trending_pages", []),
        ga4_traffic_sources=comparative_data.get("ga4", {}).get("traffic_sources", []),
        ga4_top_pages=comparative_data.get("ga4", {}).get("top_pages", []),
        ga4_devices=comparative_data.get("ga4", {}).get("devices", []),
        ga4_countries=comparative_data.get("ga4", {}).get("countries", []),
        gsc_daily=comparative_data.get("gsc_daily", []),
        rankings=comparative_data.get("rankings", {}),
        keywords=comparative_data.get("rankings", {}).get("keywords", []),
        rank_months=comparative_data.get("rank_months") or comparative_data.get("months", []),
        deltas=comparative_data.get("kpi_deltas", {}),
        ai_visibility=comparative_data.get("ai_visibility", []),
        ai_mentioned=comparative_data.get("ai_mentioned", 0),
        ai_total=comparative_data.get("ai_total", 0),
        ai_platforms=comparative_data.get("ai_platforms", 0),
        ai_by_platform=comparative_data.get("ai_by_platform", {}),
        links=comparative_data.get("links", []),
        unique_domains=comparative_data.get("unique_domains", 0),
        link_types=comparative_data.get("link_types", {}),
        activities=comparative_data.get("activities", []),
        screenshots=comparative_data.get("screenshots", []),
        gbp_shots=comparative_data.get("gbp_shots", []),
        narrative=comparative_data.get("narrative", ""),
        display_label=display_label,
        generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
        client_theme_color=client.get("theme_color", "#f5c400"),
        client_name=client.get("name", "Client"),
        client_logo_url=client.get("logo_url", ""),
        client_logo_b64=client.get("logo_b64", ""), 
        client_domain=client.get("domain", ""),
        base_url=base_url,
        agency_logo_b64=agency_logo_b64
    )


# One Chromium at a time: each is a few hundred MB, and a small server asked
# for three PDFs at once would otherwise run out of memory. The rest wait.
_PDF_SLOT = None


def _pdf_slot():
    global _PDF_SLOT
    if _PDF_SLOT is None:
        import asyncio
        _PDF_SLOT = asyncio.Semaphore(1)
    return _PDF_SLOT


async def generate_report_pdf(comparative_data: dict, client: dict, base_url: str) -> bytes:
    """
    Full pipeline:
      1. Render HTML from Jinja2 template + report data
      2. Launch Playwright Chromium (headless)
      3. Load the rendered HTML
      4. Capture PDF (A4, print backgrounds enabled)
      5. Return raw PDF bytes
    """
    from playwright.async_api import async_playwright

    html_content = render_report_html(comparative_data, client, base_url)

    async with _pdf_slot(), async_playwright() as p:
        # /dev/shm is tiny in containers; Chromium crashes on big pages without this.
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--disable-gpu"])
        try:
            # One slide is 1280×720px, which is exactly 960×540pt — the standard
            # widescreen page. Laying out at that width means what Chromium
            # measures is what the PDF prints.
            page = await browser.new_page(viewport={"width": 1280, "height": 720})

            # Set content and wait for fonts to load
            await page.set_content(html_content, wait_until="networkidle")

            # Wait for the web fonts themselves rather than a fixed pause.
            await page.evaluate("document.fonts.ready.then(() => true)")

            # Each slide is its own page at a fixed size, so the deck needs
            # none of the content-measuring the old single-sheet report did —
            # the CSS @page rule is the whole pagination story.
            await page.emulate_media(media="print")

            return await page.pdf(
                width="1280px",
                height="720px",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            await browser.close()
