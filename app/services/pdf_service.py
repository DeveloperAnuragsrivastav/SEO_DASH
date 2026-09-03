from __future__ import annotations
"""PDF generation service — renders a Jinja2 HTML template with Playwright/Chromium."""

import logging
import os
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
    """Format a number with thousand separators."""
    try:
        n = float(value) if value else 0
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.2f}"
    except (ValueError, TypeError):
        return str(value)

_jinja_env.filters["fmt"] = _fmt_filter


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
        link_types[t] = link_types.get(t, 0) + 1

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
    template = _jinja_env.get_template("report_pdf.html")
    from datetime import datetime
    
    months = comparative_data.get("months", [])
    display_label = months[0] if len(months) == 1 else f"{months[0]} \u2013 {months[-1]}" if months else "Unknown Range"
        
    import os
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

    return template.render(
        comparative_data=comparative_data,
        months=comparative_data.get("months", []),
        gsc=comparative_data.get("gsc", {}),
        ga4=comparative_data.get("ga4", {}),
        gbp=comparative_data.get("gbp", {}),
        gsc_top_pages=comparative_data.get("gsc", {}).get("top_pages", []),
        ga4_traffic_sources=comparative_data.get("ga4", {}).get("traffic_sources", []),
        ga4_top_pages=comparative_data.get("ga4", {}).get("top_pages", []),
        ga4_devices=comparative_data.get("ga4", {}).get("devices", []),
        ga4_countries=comparative_data.get("ga4", {}).get("countries", []),
        rankings=comparative_data.get("rankings", {}),
        keywords=comparative_data.get("rankings", {}).get("keywords", []),
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            # Set content and wait for fonts to load
            await page.set_content(html_content, wait_until="networkidle")

            # Small delay to ensure Google Fonts have rendered
            await page.wait_for_timeout(1500)

            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
            return pdf_bytes
        finally:
            await browser.close()
