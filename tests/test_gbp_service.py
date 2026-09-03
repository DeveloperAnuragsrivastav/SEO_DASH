"""Tests for GBP data-pulling service."""

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, SyncStatus
from app.models.metric import Metric
from app.models.sync_run import SyncRun
from app.services.gbp_service import pull_gbp_data


@pytest.fixture
def gbp_connection(db_session: Session) -> uuid.UUID:
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
            "VALUES (:id, :aid, 'Test Client', 'test.com', 'local', 'en', 10, 'active', '2026-01-01')"
        ),
        {"id": str(client_id), "aid": str(account_id)},
    )

    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, "
            "property_id, property_tz, status) "
            "VALUES (:id, :cid, 'gbp', 'platform_shared', "
            "'locations/12345', 'Asia/Kolkata', 'connected')"
        ),
        {"id": str(conn_id), "cid": str(client_id)},
    )
    db_session.commit()
    return conn_id


@patch("app.services.gbp_service._fetch_gbp_metrics")
def test_pull_gbp_data_success(
    mock_fetch: MagicMock, db_session: Session, gbp_connection: uuid.UUID
) -> None:
    # Return 1 day of data with all 8 metrics
    mock_fetch.return_value = [
        {"date": date(2026, 7, 15), "metric_key": "impressions_desktop_maps", "value": 120},
        {"date": date(2026, 7, 15), "metric_key": "impressions_desktop_search", "value": 350},
        {"date": date(2026, 7, 15), "metric_key": "impressions_mobile_maps", "value": 480},
        {"date": date(2026, 7, 15), "metric_key": "impressions_mobile_search", "value": 610},
        {"date": date(2026, 7, 15), "metric_key": "calls", "value": 25},
        {"date": date(2026, 7, 15), "metric_key": "direction_requests", "value": 42},
        {"date": date(2026, 7, 15), "metric_key": "website_clicks", "value": 88},
        {"date": date(2026, 7, 15), "metric_key": "bookings", "value": 7},
    ]

    sd = date(2026, 7, 1)
    ed = date(2026, 7, 31)

    rows_inserted = pull_gbp_data(db_session, gbp_connection, sd, ed)
    assert rows_inserted == 8

    # Verify SyncRun
    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 8

    # Verify Connection
    conn = db_session.get(Connection, gbp_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.connected

    # Verify ALL 8 metrics in database
    metrics = db_session.query(Metric).filter(Metric.provider == "gbp").all()
    assert len(metrics) == 8

    print("\n--- ACTUAL GBP DB ROWS (ALL 8 METRICS) ---")
    for m in metrics:
        print(f"metric_key={m.metric_key} | value={m.value} | captured_on={m.captured_on}")
    print("------------------------------------------")

    # Assert each of the 8 metric_keys is present with correct value
    metric_dict = {m.metric_key: float(m.value) for m in metrics}
    assert metric_dict["impressions_desktop_maps"] == 120.0
    assert metric_dict["impressions_desktop_search"] == 350.0
    assert metric_dict["impressions_mobile_maps"] == 480.0
    assert metric_dict["impressions_mobile_search"] == 610.0
    assert metric_dict["calls"] == 25.0
    assert metric_dict["direction_requests"] == 42.0
    assert metric_dict["website_clicks"] == 88.0
    assert metric_dict["bookings"] == 7.0


@patch("app.services.gbp_service._fetch_gbp_metrics")
def test_pull_gbp_data_empty_success(
    mock_fetch: MagicMock, db_session: Session, gbp_connection: uuid.UUID
) -> None:
    mock_fetch.return_value = []

    rows_inserted = pull_gbp_data(db_session, gbp_connection, date(2026, 7, 1), date(2026, 7, 31))
    assert rows_inserted == 0

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 0


@patch("app.services.gbp_service.get_google_credentials")
@patch("app.services.gbp_service.build")
def test_pull_gbp_data_retry_failure(
    mock_build: MagicMock,
    mock_creds: MagicMock,
    db_session: Session,
    gbp_connection: uuid.UUID,
) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    # Simulate HttpError on the API call
    http_resp = MagicMock()
    http_resp.status = 403
    http_resp.reason = "Permission denied for location"
    mock_service.locations().fetchMultiDailyMetricsTimeSeries().execute.side_effect = (
        HttpError(http_resp, b"Permission denied for location")
    )

    with pytest.raises(ValueError, match="GBP pull failed"):
        pull_gbp_data(db_session, gbp_connection, date(2026, 7, 1), date(2026, 7, 31))

    db_session.expire_all()

    conn = db_session.get(Connection, gbp_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.error
    assert conn.last_error is not None
    assert "Permission denied" in conn.last_error

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.failed
    assert sync_run.error is not None
    assert "Permission denied" in sync_run.error


@patch("app.services.gbp_service._fetch_gbp_metrics")
def test_gbp_pull_endpoint_integration(
    mock_fetch: MagicMock, db_session: Session, gbp_connection: uuid.UUID
) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    mock_fetch.return_value = [
        {"date": date(2026, 7, 15), "metric_key": "impressions_desktop_maps", "value": 100},
        {"date": date(2026, 7, 15), "metric_key": "calls", "value": 15},
        {"date": date(2026, 7, 15), "metric_key": "website_clicks", "value": 30},
    ]

    client = TestClient(app)
    response = client.post(
        f"/connections/{gbp_connection}/pull",
        json={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )

    print("\n--- ACTUAL GBP /pull RESPONSE BODY ---")
    print(response.json())
    print("--------------------------------------\n")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["rows_inserted"] == 3
