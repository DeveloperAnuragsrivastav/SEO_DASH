from __future__ import annotations
"""Google API clients for verification and data pulling."""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.analytics.admin import AnalyticsAdminServiceClient
from google.api_core.exceptions import InvalidArgument, PermissionDenied
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services.google_auth import get_google_credentials


def verify_gsc(property_id: str) -> None:
    """Verify access to a Google Search Console property.

    Makes a minimal searchanalytics.query call.
    Raises ValueError with the Google error message on failure.
    """
    creds = get_google_credentials()
    service = build("webmasters", "v3", credentials=creds, cache_discovery=False)

    try:
        # A minimal query to prove access.
        # Even if there's no data for this date, a 200 OK means access is granted.
        service.searchanalytics().query(
            siteUrl=property_id,
            body={
                "startDate": "2026-08-01",
                "endDate": "2026-08-01",
                "rowLimit": 1
            }
        ).execute()
    except HttpError as e:
        raise ValueError(e.reason) from e


def verify_ga4(property_id: str) -> str:
    """Verify access to a Google Analytics 4 property and fetch its timezone.

    Makes a minimal runReport call and also calls the Admin API to get the property's timezone.
    Raises ValueError with the Google error message on failure.
    Returns the time_zone string (e.g. 'America/Los_Angeles').
    """
    creds = get_google_credentials()
    data_client = BetaAnalyticsDataClient(credentials=creds)
    admin_client = AnalyticsAdminServiceClient(credentials=creds)

    # Prepend 'properties/' if missing (standard GA4 API format)
    if not property_id.startswith("properties/"):
        property_id = f"properties/{property_id}"

    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
        metrics=[Metric(name="sessions")]
    )

    try:
        data_client.run_report(request=request)
        property_obj = admin_client.get_property(name=property_id)
        return property_obj.time_zone
    except (InvalidArgument, PermissionDenied) as e:
        raise ValueError(e.message) from e
    except Exception as e:
        raise ValueError(str(e)) from e


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
        raise ValueError(e.reason) from e
