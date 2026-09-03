import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import PermissionDenied
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, SyncStatus
from app.models.metric import Metric
from app.models.sync_run import SyncRun
from app.services.date_utils import calculate_previous_month
from app.services.ga4_service import pull_ga4_data


@pytest.fixture
def ga4_connection(db_session: Session) -> uuid.UUID:
    account_id = uuid.uuid4()
    client_id = uuid.uuid4()

    db_session.execute(
        text("INSERT INTO accounts (id, name) VALUES (:id, 'Test Account')"),
        {"id": str(account_id)},
    )
    db_session.execute(
        text(
            "INSERT INTO clients (id, account_id, name, domain, business_type, "
            "locale, package_keywords, status, onboarded_at) "
            "VALUES (:id, :aid, 'Test Client', 'test.com', 'ecommerce', 'en', 10, 'active', '2026-01-01')"
        ),
        {"id": str(client_id), "aid": str(account_id)},
    )

    conn_id = uuid.uuid4()
    # Adding a connection with property_tz set to Asia/Kolkata
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, property_tz, status) "
            "VALUES (:id, :cid, 'ga4', 'platform_shared', 'properties/12345', 'Asia/Kolkata', 'connected')"
        ),
        {"id": str(conn_id), "cid": str(client_id)},
    )
    db_session.commit()
    return conn_id


def test_property_tz_date_computation() -> None:
    # Test that "last month" is correctly computed for different timezones based on a fixed timezone.utc trigger.
    # Trigger time: Jan 1, 2026 00:30 timezone.utc
    trigger_time = datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc)

    # For a timezone far West (e.g. Pacific/Honolulu timezone.utc-10), local time is Dec 31, 2025 14:30.
    # Therefore "last month" should be November 2025 (Nov 1 to Nov 30).
    start1, end1 = calculate_previous_month("Pacific/Honolulu", trigger_time)
    assert start1 == date(2025, 11, 1)
    assert end1 == date(2025, 11, 30)

    # For a timezone far East (e.g. Asia/Kolkata timezone.utc+5:30), local time is Jan 1, 2026 06:00.
    # Therefore "last month" should be December 2025 (Dec 1 to Dec 31).
    start2, end2 = calculate_previous_month("Asia/Kolkata", trigger_time)
    assert start2 == date(2025, 12, 1)
    assert end2 == date(2025, 12, 31)


@patch("app.services.ga4_service._pull_ga4_data_all_dimensions")
def test_pull_ga4_data_success(
    mock_pull: MagicMock, db_session: Session, ga4_connection: uuid.UUID
) -> None:
    # 4 rows from the mock pull:
    # Row 1: aggregate (no dimension)
    # Row 2: channel dimension
    # Row 3: device dimension
    # Row 4: country dimension
    mock_pull.return_value = [
        {
            "date": "20260801",
            "dimension_key": None,
            "dimension_value": None,
            "sessions": 100,
            "activeUsers": 90,
            "engagedSessions": 50,
            "conversions": 10,
            "purchaseRevenue": 200.5,
        },
        {
            "date": "20260801",
            "dimension_key": "sessionDefaultChannelGroup",
            "dimension_value": "Organic Search",
            "sessions": 70,
            "activeUsers": 65,
            "engagedSessions": 40,
            "conversions": 8,
            "purchaseRevenue": 150.0,
        },
        {
            "date": "20260801",
            "dimension_key": "deviceCategory",
            "dimension_value": "Mobile",
            "sessions": 60,
            "activeUsers": 50,
            "engagedSessions": 30,
            "conversions": 5,
            "purchaseRevenue": 100.0,
        },
        {
            "date": "20260801",
            "dimension_key": "country",
            "dimension_value": "India",
            "sessions": 45,
            "activeUsers": 40,
            "engagedSessions": 25,
            "conversions": 3,
            "purchaseRevenue": 75.0,
        },
    ]

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    rows_inserted = pull_ga4_data(db_session, ga4_connection, sd, ed)
    # 4 rows * 5 metrics = 20 rows in db
    assert rows_inserted == 20

    # Verify SyncRun
    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 20

    # Verify Connection
    conn = db_session.get(Connection, ga4_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.connected

    # Verify Database Rows Directly
    metrics = db_session.query(Metric).filter(Metric.provider == "ga4").all()
    assert len(metrics) == 20

    print("\n--- ACTUAL GA4 DB ROWS (ALL DIMENSIONS) ---")
    for m in metrics:
        print(
            f"metric_key={m.metric_key} | dimension_key={m.dimension_key} | "
            f"dimension_value={m.dimension_value} | value={m.value}"
        )
    print("--------------------------------------------")

    # Check channel dimension
    channel_metrics = [m for m in metrics if m.dimension_key == "sessionDefaultChannelGroup"]
    assert len(channel_metrics) == 5
    for m in channel_metrics:
        assert m.dimension_value == "Organic Search"

    # Check device dimension
    device_metrics = [m for m in metrics if m.dimension_key == "deviceCategory"]
    assert len(device_metrics) == 5
    for m in device_metrics:
        assert m.dimension_value == "Mobile"

    # Check country dimension
    country_metrics = [m for m in metrics if m.dimension_key == "country"]
    assert len(country_metrics) == 5
    for m in country_metrics:
        assert m.dimension_value == "India"

    # Check aggregate (no dimension)
    agg_metrics = [m for m in metrics if m.dimension_key is None]
    assert len(agg_metrics) == 5


@patch("app.services.ga4_service._pull_ga4_data_all_dimensions")
def test_pull_ga4_data_empty_success(
    mock_pull: MagicMock, db_session: Session, ga4_connection: uuid.UUID
) -> None:
    # Empty response
    mock_pull.return_value = []

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    rows_inserted = pull_ga4_data(db_session, ga4_connection, sd, ed)
    assert rows_inserted == 0

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 0


@patch("app.services.ga4_service.get_google_credentials")
@patch("app.services.ga4_service.BetaAnalyticsDataClient")
def test_pull_ga4_data_retry_failure(
    mock_client_class: MagicMock, mock_creds: MagicMock, db_session: Session, ga4_connection: uuid.UUID
) -> None:
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Simulate a permission denied error
    mock_client.run_report.side_effect = PermissionDenied("User does not have sufficient permissions")

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    with pytest.raises(ValueError, match="GA4 pull failed: User does not have sufficient permissions"):
        pull_ga4_data(db_session, ga4_connection, sd, ed)

    db_session.expire_all()

    conn = db_session.get(Connection, ga4_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.error
    assert conn.last_error is not None
    assert "User does not have sufficient permissions" in conn.last_error

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.failed
    assert sync_run.error is not None
    assert "User does not have sufficient permissions" in sync_run.error

    # Assert it retried (1 initial + 2 retries = 3 calls total)
    assert mock_client.run_report.call_count == 3


@patch("app.services.ga4_service._pull_ga4_data_all_dimensions")
def test_ga4_pull_endpoint_integration(
    mock_pull: MagicMock, db_session: Session, ga4_connection: uuid.UUID
) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    mock_pull.return_value = [
        {
            "date": "20260801",
            "dimension_key": "country",
            "dimension_value": "United States",
            "sessions": 500,
            "activeUsers": 450,
            "engagedSessions": 300,
            "conversions": 25,
            "purchaseRevenue": 1500.00,
        }
    ]

    client = TestClient(app)
    response = client.post(
        f"/connections/{ga4_connection}/pull",
        json={"start_date": "2026-08-01", "end_date": "2026-08-01"}
    )

    print("\n--- ACTUAL GA4 /pull RESPONSE BODY ---")
    print(response.json())
    print("--------------------------------------\n")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["rows_inserted"] == 5
