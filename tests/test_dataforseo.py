from __future__ import annotations
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from app.models.connection import AccessMode, Connection, ConnectionStatus
from app.services.dataforseo_auth import validate_dataforseo_credentials

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

@patch("app.services.dataforseo_auth.httpx.get")
def test_validate_dataforseo_credentials_success(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status_code": 20000,
        "status_message": "Ok.",
        "cost": 0
    }
    mock_get.return_value = mock_response

    assert validate_dataforseo_credentials("test_user", "test_pass") is True
    
    # Assert Authorization header was sent correctly
    args, kwargs = mock_get.call_args
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["Authorization"].startswith("Basic ")


@patch("app.services.dataforseo_auth.httpx.get")
def test_validate_dataforseo_credentials_auth_failure(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status_code": 40100,
        "status_message": "Authentication failed",
        "cost": 0
    }
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="DataForSEO authentication failed: Code 40100, Message: Authentication failed"):
        validate_dataforseo_credentials("bad_user", "bad_pass")


@patch("app.services.dataforseo_auth.httpx.get")
def test_validate_dataforseo_credentials_http_failure(mock_get: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="DataForSEO API error: HTTP 403"):
        validate_dataforseo_credentials("bad_user", "bad_pass")


@patch("app.routes.connections.validate_dataforseo_credentials")
def test_create_dataforseo_client_owned_success(
    mock_validate: MagicMock, test_client_id: uuid.UUID, db_session: Session
) -> None:
    mock_validate.return_value = True

    response = client.post(
        f"/clients/{test_client_id}/connections/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "my_client_login",
            "password": "my_client_password"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "dataforseo"
    assert data["access_mode"] == "client_owned"
    assert data["status"] == "connected"
    
    conn_id = data["id"]
    conn = db_session.get(Connection, uuid.UUID(conn_id))
    assert conn is not None
    assert conn.credentials is not None
    
    # Validate envelope encryption: Ensure plain text is nowhere to be found in raw DB value
    raw_creds_str = str(conn.credentials)
    print("\n--- ACTUAL ENCRYPTED DB VALUE ---")
    print(raw_creds_str)
    print("---------------------------------")
    
    assert "my_client_login" not in raw_creds_str
    assert "my_client_password" not in raw_creds_str
    assert "encrypted_data" in raw_creds_str
    assert "encrypted_dek" in raw_creds_str


@patch("app.routes.connections.validate_dataforseo_credentials")
def test_create_dataforseo_client_owned_failure(
    mock_validate: MagicMock, test_client_id: uuid.UUID
) -> None:
    mock_validate.side_effect = ValueError("DataForSEO authentication failed: Code 40100, Message: Auth failed")

    response = client.post(
        f"/clients/{test_client_id}/connections/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "bad",
            "password": "bad"
        }
    )

    assert response.status_code == 400
    assert "Auth failed" in response.json()["detail"]


@patch("app.routes.connections.validate_dataforseo_credentials")
def test_update_dataforseo_access_mode_transitions(
    mock_validate: MagicMock, test_client_id: uuid.UUID, db_session: Session
) -> None:
    mock_validate.return_value = True

    # 1. Create as client_owned
    response = client.post(
        f"/clients/{test_client_id}/connections/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "login_1",
            "password": "password_1"
        }
    )
    assert response.status_code == 201
    conn_id = response.json()["id"]

    # 2. Switch to platform_shared
    response2 = client.put(
        f"/connections/{conn_id}/dataforseo",
        json={
            "access_mode": "platform_shared"
        }
    )
    assert response2.status_code == 200
    assert response2.json()["access_mode"] == "platform_shared"

    conn = db_session.get(Connection, uuid.UUID(conn_id))
    # Confirm credentials are wiped
    assert conn.credentials is None

    # 3. Switch back to client_owned with new credentials
    response3 = client.put(
        f"/connections/{conn_id}/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "login_2",
            "password": "password_2"
        }
    )
    assert response3.status_code == 200
    assert response3.json()["access_mode"] == "client_owned"
    
    db_session.refresh(conn)
    assert conn.credentials is not None
    assert "encrypted_data" in conn.credentials


@patch("app.routes.connections.validate_dataforseo_credentials")
def test_update_dataforseo_validation_failure_sets_error_status(
    mock_validate: MagicMock, test_client_id: uuid.UUID, db_session: Session
) -> None:
    mock_validate.return_value = True

    # Create as client_owned successfully
    response = client.post(
        f"/clients/{test_client_id}/connections/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "login_1",
            "password": "password_1"
        }
    )
    assert response.status_code == 201
    conn_id = response.json()["id"]

    # Update fails validation
    mock_validate.side_effect = ValueError("DataForSEO authentication failed: Code 40100")
    response2 = client.put(
        f"/connections/{conn_id}/dataforseo",
        json={
            "access_mode": "client_owned",
            "login": "login_bad",
            "password": "password_bad"
        }
    )
    assert response2.status_code == 400

    # Ensure DB row reflects error state
    conn = db_session.get(Connection, uuid.UUID(conn_id))
    assert conn.status == ConnectionStatus.error
    assert "DataForSEO authentication failed: Code 40100" in conn.last_error
