import pytest
import uuid
from fastapi.testclient import TestClient

from app.dependencies import get_current_user

def test_users_crud_admin(client, test_users, app):
    """Test full CRUD cycle for agency_admin."""
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    
    # 1. Create a user
    res = client.post("/users", json={
        "email": "newuser@test.com",
        "password": "testpassword123",
        "role": "agency_staff"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "agency_staff"
    assert data["is_active"] is True
    user_id = data["id"]
    
    # 2. List users
    res = client.get("/users")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    
    # 3. Promote user to admin
    res = client.put(f"/users/{user_id}/role", json={
        "role": "agency_admin"
    })
    assert res.status_code == 200
    assert res.json()["role"] == "agency_admin"
    
    # 4. Deactivate user
    res = client.put(f"/users/{user_id}/deactivate")
    assert res.status_code == 200
    assert res.json()["is_active"] is False


def test_users_rbac_staff_forbidden(client, test_users, app):
    """Test that agency_staff gets 403 on user management."""
    # Override dependency to use staff user
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    
    res = client.get("/users")
    assert res.status_code == 403
    
    res = client.post("/users", json={
        "email": "staff_tries_create@test.com",
        "password": "pwd",
        "role": "agency_staff"
    })
    assert res.status_code == 403
    
    dummy_id = str(uuid.uuid4())
    res = client.put(f"/users/{dummy_id}/role", json={"role": "agency_admin"})
    assert res.status_code == 403
    
    res = client.put(f"/users/{dummy_id}/deactivate")
    assert res.status_code == 403
