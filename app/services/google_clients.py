from __future__ import annotations
"""Google API clients for verification and data pulling."""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.analytics.admin import AnalyticsAdminServiceClient
import re

from google.api_core.exceptions import GoogleAPICallError, InvalidArgument, NotFound, PermissionDenied
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.google_auth import get_google_credentials


# ── Telling people what is actually wrong ───────────────────────────────────
# Google answers every refusal with a terse reason ("Forbidden", "User does not
# have sufficient permission…"). These turn the common ones into what to do.

def service_account_email() -> str:
    """The address clients must add to their Google properties."""
    try:
        return getattr(get_google_credentials(), "service_account_email", "") or ""
    except Exception:
        return ""


def _access_hint(what: str) -> str:
    email = service_account_email()
    who = f" {email}" if email else " the service account"
    return f"Add{who} to {what}"


def _explain(provider: str, status_code: int | None, text: str, property_id: str) -> str:
    low = (text or "").lower()
    if "has not been used" in low or "is disabled" in low or "service_disabled" in low or "accessnotconfigured" in low:
        api = "Search Console API" if provider == "gsc" else "Google Analytics Data API and Admin API"
        return f"The {api} is turned off in the Google Cloud project behind the service account. Enable it in Google Cloud → APIs & Services, then press Verify."
    if status_code == 404 or "not found" in low or "not_found" in low:
        return (f"No {'Search Console property' if provider == 'gsc' else 'Analytics property'} “{property_id}” exists. "
                "Check the address or ID for typos.")
    if status_code in (401, 403) or "permission" in low or "forbidden" in low:
        if provider == "gbp":
            return (f"No access to Business Profile location {property_id} yet. "
                    + _access_hint("the Business Profile as a Manager") + ", then press Verify.")
        if provider == "gsc":
            return (f"No access to “{property_id}” yet. "
                    + _access_hint("this property in Search Console → Settings → Users and permissions (Restricted is enough)") + ", then press Verify.")
        return (f"No access to Analytics property {property_id} yet. "
                + _access_hint("this property in Analytics → Admin → Property access management, as Viewer") + ", then press Verify.")
    if status_code == 400 or "invalid" in low:
        return f"Google did not accept “{property_id}” as a property: {text}"
    return f"Google refused the request: {text}"


def explain_pull_error(provider: str, e: BaseException, property_id: str) -> str:
    """A failed data pull (GSC, GA4 or GBP), in words a person can act on."""
    if isinstance(e, HttpError):
        return _explain(provider, e.resp.status if e.resp else None, str(e.reason or e), property_id)
    if isinstance(e, GoogleAPICallError):
        status_code = 403 if isinstance(e, PermissionDenied) else 404 if isinstance(e, NotFound) else \
            400 if isinstance(e, InvalidArgument) else getattr(e, "code", None)
        return _explain(provider, status_code if isinstance(status_code, int) else None,
                        getattr(e, "message", str(e)), property_id)
    if isinstance(e, ValueError):
        return str(e)
    return f"Could not reach Google — try again in a minute. ({type(e).__name__})"


# ── Search Console ──────────────────────────────────────────────────────────

def _gsc_service():
    return build("webmasters", "v3", credentials=get_google_credentials(), cache_discovery=False)


def gsc_sites() -> list[dict]:
    """Every Search Console property the service account can read:
    [{"property": "sc-domain:x.com", "permission": "siteRestrictedUser"}]."""
    try:
        entries = (_gsc_service().sites().list().execute() or {}).get("siteEntry") or []
    except HttpError as e:
        raise ValueError(_explain("gsc", e.resp.status if e.resp else None, str(e.reason or e), "the property list")) from e
    return [{"property": e.get("siteUrl"), "permission": e.get("permissionLevel")}
            for e in entries if e.get("siteUrl") and e.get("permissionLevel") != "siteUnverifiedUser"]


def _gsc_domain(raw: str) -> str:
    """The bare domain inside anything typed: foodbazaar.co.uk,
    https://www.foodbazaar.co.uk/page, sc-domain:foodbazaar.co.uk → foodbazaar.co.uk."""
    text = (raw or "").strip().strip("/").lower()
    if text.startswith("sc-domain:"):
        text = text[len("sc-domain:"):]
    text = re.sub(r"^[a-z]+://", "", text)
    text = text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].split(":", 1)[0]
    return text[4:] if text.startswith("www.") else text


def gsc_candidates(raw: str) -> list[str]:
    """Every Search Console property name the typed value could mean, most
    likely first: exactly as typed (when it is a full address), the domain
    property, then the https/http and www/non-www prefixes."""
    text = (raw or "").strip()
    domain = _gsc_domain(text)
    out = []
    if re.match(r"^https?://", text, re.I):
        out.append(text if text.endswith("/") else text + "/")
    if text.lower().startswith("sc-domain:"):
        out.append(f"sc-domain:{domain}")
    if domain:
        out += [f"sc-domain:{domain}", f"https://{domain}/", f"https://www.{domain}/",
                f"http://{domain}/", f"http://www.{domain}/"]
    seen = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def resolve_gsc_property(raw: str) -> str:
    """The Search Console property a typed value refers to, among those the
    service account can read. Raises ValueError saying what to do when none
    matches."""
    domain = _gsc_domain(raw)
    if not domain or "." not in domain or " " in domain:
        raise ValueError(f"“{raw}” is not a website address. Type it like foodbazaar.co.uk or https://foodbazaar.co.uk/.")
    readable = {s["property"].lower(): s["property"] for s in gsc_sites()}
    for cand in gsc_candidates(raw):
        if cand.lower() in readable:
            return readable[cand.lower()]
    # Readable, but under a path (https://site.com/blog/)?
    for low, prop in readable.items():
        if _gsc_domain(prop) == domain:
            return prop
    raise ValueError(
        f"No Search Console property for {domain} is shared with the service account yet. "
        + _access_hint(f"{domain} in Search Console → Settings → Users and permissions (Restricted is enough)")
        + ", then press Verify.")


def verify_gsc(property_id: str) -> str:
    """Find the Search Console property behind what was typed and prove it can
    be read. Returns the exact property name to store. Raises ValueError with
    what to do on failure."""
    prop = resolve_gsc_property(property_id)
    try:
        _gsc_service().searchanalytics().query(
            siteUrl=prop, body={"startDate": "2026-08-01", "endDate": "2026-08-01", "rowLimit": 1}).execute()
    except HttpError as e:
        raise ValueError(_explain("gsc", e.resp.status if e.resp else None, str(e.reason or e), prop)) from e
    return prop


# ── Google Analytics 4 ──────────────────────────────────────────────────────

def normalize_ga4(raw: str) -> str:
    """The numeric GA4 property id inside anything typed: 439694882,
    properties/439694882, or a pasted Analytics address (…/p439694882/…).
    Raises ValueError for the IDs people confuse it with."""
    text = (raw or "").strip()
    if re.fullmatch(r"G-[A-Z0-9]{4,}", text, re.I):
        raise ValueError(f"“{text}” is a measurement ID (for the website tag), not the property ID. "
                         "Find the number under Analytics → Admin → Property details → Property ID.")
    if re.fullmatch(r"UA-\d+-\d+", text, re.I):
        raise ValueError("That is a Universal Analytics ID — Universal Analytics was switched off by Google. "
                         "Use the GA4 property's numeric ID (Admin → Property details).")
    m = (re.fullmatch(r"(?:properties/)?(\d{6,12})", text)
         or re.search(r"[/#a]p(\d{6,12})(?:\b|/)", text)
         or re.search(r"properties/(\d{6,12})", text))
    if not m:
        raise ValueError(f"“{text}” is not a GA4 property ID. It is a number like 439694882 "
                         "(Analytics → Admin → Property details), or paste the Analytics address from your browser.")
    return m.group(1)


def ga4_properties() -> list[dict]:
    """Every GA4 property the service account can read:
    [{"property": "439694882", "name": "Food Bazaar – GA4", "account": "Food Bazaar"}]."""
    admin_client = AnalyticsAdminServiceClient(credentials=get_google_credentials())
    out = []
    try:
        for acct in admin_client.list_account_summaries():
            for p in acct.property_summaries:
                out.append({"property": p.property.split("/")[-1], "name": p.display_name, "account": acct.display_name})
    except GoogleAPICallError as e:
        raise ValueError(_explain("ga4", getattr(e, "code", None), getattr(e, "message", str(e)), "the property list")) from e
    return out


def verify_ga4(property_id: str) -> str:
    """Verify access to a GA4 property and fetch its timezone (e.g.
    'Europe/London'). Raises ValueError with what to do on failure."""
    number = normalize_ga4(property_id)
    name = f"properties/{number}"
    creds = get_google_credentials()
    data_client = BetaAnalyticsDataClient(credentials=creds)
    admin_client = AnalyticsAdminServiceClient(credentials=creds)
    request = RunReportRequest(
        property=name,
        date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
        metrics=[Metric(name="sessions")],
    )
    try:
        data_client.run_report(request=request)
        return admin_client.get_property(name=name).time_zone
    except GoogleAPICallError as e:
        code = getattr(e, "code", None)
        status_code = {7: 403, 5: 404, 3: 400}.get(code, code) if isinstance(code, int) else getattr(code, "value", None)
        if isinstance(e, PermissionDenied):
            status_code = 403
        elif isinstance(e, NotFound):
            status_code = 404
        elif isinstance(e, InvalidArgument):
            status_code = 400
        raise ValueError(_explain("ga4", status_code, getattr(e, "message", str(e)), number)) from e


def verify_gbp(property_id: str) -> None:
    """Verify access to a Google Business Profile location.

    Makes a minimal call to the Business Profile Performance API.
    Raises ValueError with the Google error message on failure.
    """
    creds = get_google_credentials()
    # The performance API is businessprofileperformance
    service = build("businessprofileperformance", "v1", credentials=creds, cache_discovery=False)

    # Prepend 'locations/' if missing
    if not property_id.startswith("locations/"):
        property_id = f"locations/{property_id}"

    try:
        # A minimal call: get daily metrics time series for a single day
        service.locations().getDailyMetricsTimeSeries(
            name=property_id,
            dailyMetric="WEBSITE_CLICKS",
            dailyRange_startDate_year=2026,
            dailyRange_startDate_month=1,
            dailyRange_startDate_day=1,
            dailyRange_endDate_year=2026,
            dailyRange_endDate_month=1,
            dailyRange_endDate_day=1,
        ).execute()
    except HttpError as e:
        raise ValueError(_explain("gbp", e.resp.status if e.resp else None, str(e.reason or e), property_id)) from e
