from __future__ import annotations
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.dependencies import get_current_user
from app.models.client import Client
import uuid
import datetime

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_auth_override():
    """Remove the global default mock auth so we can test actual JWT behavior."""
    app.dependency_overrides.pop(get_current_user, None)
    yield
    # No need to restore, conftest handles it per test anyway

def test_login_success(test_users, db_session):
    res = client.post("/auth/login", data={"username": "admin@test.com", "password": "pass"})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["token_type"] == "bearer"

def test_login_invalid_password(test_users):
    res = client.post("/auth/login", data={"username": "admin@test.com", "password": "wrong"})
    assert res.status_code == 401

def test_login_nonexistent_user():
    res = client.post("/auth/login", data={"username": "nobody@test.com", "password": "pass"})
    assert res.status_code == 401

def test_jwt_missing():
    # Attempt to hit an endpoint without any token
    res = client.get("/clients/00000000-0000-0000-0000-000000000000/connections")
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"

def test_jwt_malformed():
    res = client.get("/clients/00000000-0000-0000-0000-000000000000/connections", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Could not validate credentials"

def test_jwt_expired(test_users):
    import jwt
    from app.config import settings
    # Create a token that expired 1 hour ago
    expire = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    to_encode = {"sub": test_users["admin"].email, "exp": expire}
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    res = client.get("/clients/00000000-0000-0000-0000-000000000000/connections", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Token has expired"

def test_rbac_connections_agency_staff_rejected(staff_auth_headers):
    # agency_staff cannot access connections
    res = client.get("/clients/00000000-0000-0000-0000-000000000000/connections", headers=staff_auth_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "Not enough permissions"

def test_rbac_connections_agency_admin_allowed(admin_auth_headers, test_users, db_session):
    # Need to create a client first so it doesn't fail on client lookup, wait, connections list doesn't strictly check if client exists, but let's assume it returns empty list
    client_uuid = uuid.uuid4()
    db_session.add(Client(id=client_uuid, account_id=test_users["admin"].account_id, name="Test", domain="example.com", business_type="local", locale="en-US", package_keywords=100, status="active", onboarded_at=datetime.date.today()))
    db_session.commit()
    
    res = client.get(f"/clients/{client_uuid}/connections", headers=admin_auth_headers)
    assert res.status_code == 200
    assert res.json() == []

def test_rbac_publish_report(admin_auth_headers, staff_auth_headers, test_users, db_session):
    from app.models.report_month import ReportMonth
    from app.models.enums import ReportStatus
    
    client_id = uuid.uuid4()
    db_session.add(Client(id=client_id, account_id=test_users["admin"].account_id, name="Test Pub", domain="example.com", business_type="local", locale="en-US", package_keywords=100, status="active", onboarded_at=datetime.date.today()))
    
    month = datetime.date(2026, 8, 1)
    rep = ReportMonth(client_id=client_id, month=month, status=ReportStatus.draft, snapshot={}, narrative="draft")
    db_session.add(rep)
    db_session.commit()
    
    # Staff cannot publish
    res = client.post(f"/clients/{client_id}/reports/2026-08/publish", headers=staff_auth_headers)
    assert res.status_code == 403
    
    # Admin CAN publish
    res = client.post(f"/clients/{client_id}/reports/2026-08/publish", headers=admin_auth_headers)
    assert res.status_code == 200
    
    # Check published_by
    db_session.refresh(rep)
    assert rep.status == ReportStatus.published
    assert rep.published_by == test_users["admin"].id
    
    # Print the published_by for the user evidence
    print(f"\\n\\nEVIDENCE: published_by = {rep.published_by} (matches admin user id: {test_users['admin'].id})\\n")
