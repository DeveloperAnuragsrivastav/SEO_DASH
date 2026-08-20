from __future__ import annotations
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.enums import ConnectionStatus, SyncStatus
from app.models.metric import Metric
from app.models.sync_run import SyncRun
from app.services.gsc_service import pull_gsc_data


@pytest.fixture
def gsc_connection(db_session: Session) -> uuid.UUID:
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
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gsc', 'platform_shared', 'https://test.com', 'connected')"
        ),
        {"id": str(conn_id), "cid": str(client_id)},
    )
    db_session.commit()
    return conn_id


@patch("app.services.gsc_service._pull_gsc_data_with_retry")
def test_pull_gsc_data_success(
    mock_pull: MagicMock, db_session: Session, gsc_connection: uuid.UUID
) -> None:
    # Mock returning 1 row (it will be translated into 4 metrics: clicks, impressions, ctr, position)
    mock_pull.return_value = [
        {
            "keys": ["2026-08-01"],
            "clicks": 100,
            "impressions": 500,
            "ctr": 0.2,
            "position": 5.5,
            "dimension_key": None,
            "dimension_value": None,
        }
    ]

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    rows_inserted = pull_gsc_data(db_session, gsc_connection, sd, ed)
    assert rows_inserted == 4

    # Verify SyncRun
    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 4

    # Verify Connection
    conn = db_session.get(Connection, gsc_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.connected

    # Verify Metrics
    metrics = db_session.query(Metric).all()
    assert len(metrics) == 4
    metric_keys = [m.metric_key for m in metrics]
    assert sorted(metric_keys) == ["clicks", "ctr", "impressions", "position"]


@patch("app.services.gsc_service._pull_gsc_data_with_retry")
def test_pull_gsc_data_empty_success(
    mock_pull: MagicMock, db_session: Session, gsc_connection: uuid.UUID
) -> None:
    # Empty response
    mock_pull.return_value = []

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    rows_inserted = pull_gsc_data(db_session, gsc_connection, sd, ed)
    assert rows_inserted == 0

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 0


@patch("app.services.gsc_service.get_google_credentials")
@patch("app.services.gsc_service.build")
def test_pull_gsc_data_retry_failure(
    mock_build: MagicMock, mock_creds: MagicMock, db_session: Session, gsc_connection: uuid.UUID
) -> None:
    # We want to test that a total failure sets connection to error.
    # Tenacity will retry 3 times internally.
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    resp = Response({"status": "403"})
    error_content = b'{"error": {"message": "Permission denied"}}'

    mock_service.searchanalytics().query().execute.side_effect = HttpError(resp, error_content)

    sd = date(2026, 8, 1)
    ed = date(2026, 8, 1)

    with pytest.raises(ValueError, match="GSC pull failed: Permission denied"):
        pull_gsc_data(db_session, gsc_connection, sd, ed)

    # Validate db state
    # Wait, because we hit a ValueError, the db.rollback() was called inside the service
    # and then we committed the error state. We need to fetch from a clean state.
    db_session.expire_all()

    conn = db_session.get(Connection, gsc_connection)
    assert conn is not None
    assert conn.status == ConnectionStatus.error
    assert conn.last_error == "Permission denied"

    sync_run = db_session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()
    assert sync_run is not None
    assert sync_run.status == SyncStatus.failed
    assert sync_run.error == "Permission denied"

    # Assert it retried (1 initial + 2 retries = 3 calls)
    assert mock_build.call_count == 3


@patch("app.services.gsc_service._pull_gsc_data_with_retry")
def test_pull_endpoint_integration(
    mock_pull: MagicMock, db_session: Session, gsc_connection: uuid.UUID
) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    mock_pull.return_value = [
        {
            "keys": ["2026-08-01"],
            "clicks": 150,
            "impressions": 800,
            "ctr": 0.18,
            "position": 3.2,
            "dimension_key": None,
            "dimension_value": None,
        }
    ]

    client = TestClient(app)
    response = client.post(
        f"/connections/{gsc_connection}/pull",
        json={"start_date": "2026-08-01", "end_date": "2026-08-01"}
    )

    print("\n--- ACTUAL /pull RESPONSE BODY ---")
    print(response.json())
    print("----------------------------------\n")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["rows_inserted"] == 4


