from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user

client = TestClient(app)

def test_connections_rbac(test_users):
    # Admin creates client
    app.dependency_overrides[get_current_user] = lambda: test_users["admin"]
    res = client.post(
        "/clients",
        json={
            "name": "Connection RBAC Test",
            "domain": "rbac.com",
            "business_type": "saas",
            "locale": "en-US",
            "package_keywords": 10,
            "status": "active"
        }
    )
    assert res.status_code == 201
    c_id = res.json()["id"]

    # Admin creates a connection
    conn_res = client.post(
        f"/clients/{c_id}/connections",
        json={"provider": "gsc", "property_id": "sc-domain:rbac.com"}
    )
    assert conn_res.status_code == 201
    conn_id = conn_res.json()["id"]

    # Staff can read connections
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    read_res = client.get(f"/clients/{c_id}/connections")
    assert read_res.status_code == 200
    assert len(read_res.json()) == 1

    # Staff CANNOT create a connection
    create_res = client.post(
        f"/clients/{c_id}/connections",
        json={"provider": "ga4", "property_id": "properties/123"}
    )
    assert create_res.status_code == 403

    # Staff CANNOT verify a connection
    verify_res = client.post(f"/connections/{conn_id}/verify")
    assert verify_res.status_code == 403

    # Staff CANNOT update a connection
    update_res = client.patch(
        f"/connections/{conn_id}",
        json={"property_id": "sc-domain:hacked.com"}
    )
    assert update_res.status_code == 403
