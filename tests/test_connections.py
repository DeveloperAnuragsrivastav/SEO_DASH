from __future__ import annotations
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import InvalidArgument, PermissionDenied
from googleapiclient.errors import HttpError
from httplib2 import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app

client = TestClient(app)


@pytest.fixture
def test_client_id(db_session: Session) -> uuid.UUID:
    """Insert a test account and client, return client_id."""
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
    db_session.commit()
    return client_id


@pytest.fixture
def gsc_connection(db_session: Session, test_client_id: uuid.UUID) -> uuid.UUID:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gsc', 'platform_shared', 'https://test.com', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()
    return conn_id


def test_create_connection(test_client_id: uuid.UUID) -> None:
    response = client.post(
        f"/clients/{test_client_id}/connections",
        json={"provider": "ga4", "property_id": "123456", "property_tz": "timezone.utc"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "ga4"
    assert data["property_id"] == "123456"
    assert data["property_tz"] == "timezone.utc"
    assert data["status"] == "not_connected"


def test_update_connection_resets_status(
    test_client_id: uuid.UUID, gsc_connection: uuid.UUID, db_session: Session
) -> None:
    # Manually set to connected
    db_session.execute(
        text("UPDATE connections SET status = 'connected' WHERE id = :id"),
        {"id": str(gsc_connection)},
    )
    db_session.commit()

    response = client.patch(
        f"/connections/{gsc_connection}", json={"property_id": "https://new.com"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "not_connected"
    assert response.json()["property_id"] == "https://new.com"


@patch("app.routes.connections.verify_gsc")
def test_verify_gsc_wrapper_success(
    mock_verify: MagicMock, test_client_id: uuid.UUID, gsc_connection: uuid.UUID
) -> None:
    mock_verify.return_value = None
    response = client.post(f"/connections/{gsc_connection}/verify")
    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    mock_verify.assert_called_once_with("https://test.com")


@patch("app.routes.connections.verify_gsc")
def test_verify_gsc_wrapper_failure(
    mock_verify: MagicMock, test_client_id: uuid.UUID, gsc_connection: uuid.UUID
) -> None:
    mock_verify.side_effect = ValueError(
        "User does not have sufficient permission for site 'https://test.com'."
    )
    response = client.post(f"/connections/{gsc_connection}/verify")
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "User does not have sufficient permission for site 'https://test.com'."
    )

    # DB check
    conn_res = client.get(f"/clients/{test_client_id}/connections").json()
    assert conn_res[0]["status"] == "error"
    assert (
        conn_res[0]["last_error"]
        == "User does not have sufficient permission for site 'https://test.com'."
    )


# Real tests that mock the Google API clients directly


@patch("app.services.google_clients.build")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_gsc_real_mock_error(
    mock_creds: MagicMock,
    mock_build: MagicMock,
    test_client_id: uuid.UUID,
    gsc_connection: uuid.UUID,
) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    # Simulate HttpError
    resp = Response({"status": "403"})
    error_content = b'{"error": {"message": "Permission denied"}}'
    mock_service.searchanalytics().query().execute.side_effect = HttpError(
        resp, error_content
    )

    response = client.post(f"/connections/{gsc_connection}/verify")
    assert response.status_code == 400
    assert response.json()["detail"] == "Permission denied"


@patch("app.services.google_clients.AnalyticsAdminServiceClient")
@patch("app.services.google_clients.BetaAnalyticsDataClient")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_ga4_invalid_argument(
    mock_creds: MagicMock,
    mock_data_client: MagicMock,
    mock_admin_client: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'ga4', 'platform_shared', '12345', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_instance = mock_data_client.return_value
    mock_instance.run_report.side_effect = InvalidArgument("Property ID not found")

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 400
    assert response.json()["detail"] == "Property ID not found"


@patch("app.services.google_clients.AnalyticsAdminServiceClient")
@patch("app.services.google_clients.BetaAnalyticsDataClient")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_ga4_permission_denied(
    mock_creds: MagicMock,
    mock_data_client: MagicMock,
    mock_admin_client: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'ga4', 'platform_shared', 'properties/12345', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_instance = mock_data_client.return_value
    mock_instance.run_report.side_effect = PermissionDenied(
        "User does not have sufficient permissions"
    )

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 400
    assert response.json()["detail"] == "User does not have sufficient permissions"


@patch("app.services.google_clients.build")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_gbp_success(
    mock_creds: MagicMock,
    mock_build: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gbp', 'platform_shared', '12345', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_service = MagicMock()
    mock_build.return_value = mock_service

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 200
    assert response.json()["status"] == "connected"

    # check if prepended locations/ properly
    mock_service.locations().getDailyMetricsTimeSeries.assert_called_once()
    assert (
        mock_service.locations().getDailyMetricsTimeSeries.call_args[1]["name"]
        == "locations/12345"
    )


@patch("app.services.google_clients.build")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_gbp_failure(
    mock_creds: MagicMock,
    mock_build: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gbp', 'platform_shared', '12345', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_service = MagicMock()
    mock_build.return_value = mock_service

    resp = Response({"status": "403"})
    error_content = b'{"error": {"message": "Permission denied"}}'
    mock_service.locations().getDailyMetricsTimeSeries.side_effect = HttpError(
        resp, error_content
    )

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 400
    assert response.json()["detail"] == "Permission denied"

    # DB check
    conn_res = client.get(f"/clients/{test_client_id}/connections").json()
    # Find the newly created one
    for c in conn_res:
        if c["id"] == str(conn_id):
            assert c["status"] == "error"
            assert c["last_error"] == "Permission denied"


@patch("app.services.google_clients.build")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_gbp_normalization_no_prefix(
    mock_creds: MagicMock,
    mock_build: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gbp', 'platform_shared', '1234567', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_service = MagicMock()
    mock_build.return_value = mock_service

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 200
    assert (
        mock_service.locations().getDailyMetricsTimeSeries.call_args[1]["name"]
        == "locations/1234567"
    )


@patch("app.services.google_clients.build")
@patch("app.services.google_clients.get_google_credentials")
def test_verify_gbp_normalization_with_prefix(
    mock_creds: MagicMock,
    mock_build: MagicMock,
    db_session: Session,
    test_client_id: uuid.UUID,
) -> None:
    conn_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO connections (id, client_id, provider, access_mode, property_id, status) "
            "VALUES (:id, :cid, 'gbp', 'platform_shared', 'locations/1234567', 'not_connected')"
        ),
        {"id": str(conn_id), "cid": str(test_client_id)},
    )
    db_session.commit()

    mock_service = MagicMock()
    mock_build.return_value = mock_service

    response = client.post(f"/connections/{conn_id}/verify")
    assert response.status_code == 200
    assert (
        mock_service.locations().getDailyMetricsTimeSeries.call_args[1]["name"]
        == "locations/1234567"
    )
