import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user

client = TestClient(app)

def test_create_client_admin(test_users):
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    response = client.post(
        "/clients",
        json={
            "name": "Acme Corp",
            "domain": "acme.com",
            "business_type": "saas",
            "locale": "en-US",
            "package_keywords": 50,
            "status": "active"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert "id" in data

def test_create_client_staff_forbidden(test_users):
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    response = client.post(
        "/clients",
        json={
            "name": "Acme Corp 2",
            "domain": "acme2.com",
            "business_type": "saas",
            "locale": "en-US",
            "package_keywords": 50,
            "status": "active"
        }
    )
    assert response.status_code == 403

def test_get_clients(test_users):
    # Admin creates client
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    client.post(
        "/clients",
        json={
            "name": "List Test Client",
            "domain": "list.com",
            "business_type": "local",
            "locale": "en-US",
            "package_keywords": 10,
            "status": "active"
        }
    )
    
    # Staff can read list
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    response = client.get("/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any(c["name"] == "List Test Client" for c in data)

def test_update_client_admin(test_users):
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    res1 = client.post(
        "/clients",
        json={
            "name": "Update Me",
            "domain": "up.com",
            "business_type": "ecommerce",
            "locale": "en-IN",
            "package_keywords": 25,
            "status": "active"
        }
    )
    assert res1.status_code == 201
    c_id = res1.json()["id"]
    
    res2 = client.put(
        f"/clients/{c_id}",
        json={"name": "Updated Corp", "status": "paused"}
    )
    assert res2.status_code == 200
    data = res2.json()
    assert data["name"] == "Updated Corp"
    assert data["status"] == "paused"

def test_update_client_staff_forbidden(test_users):
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    res1 = client.post(
        "/clients",
        json={
            "name": "Staff Update Me",
            "domain": "staff.com",
            "business_type": "ecommerce",
            "locale": "en-IN",
            "package_keywords": 25,
            "status": "active"
        }
    )
    assert res1.status_code == 201
    c_id = res1.json()["id"]
    
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    res2 = client.put(
        f"/clients/{c_id}",
        json={"name": "Hacked"}
    )
    assert res2.status_code == 403
