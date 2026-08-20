from __future__ import annotations
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.models.keyword import Keyword

client = TestClient(app)

def test_deactivate_keyword(test_users, db_session):
    app.dependency_overrides[get_current_user] = lambda: test_users["staff"]
    
    from app.models.client import Client
    test_client = Client(
        account_id=test_users["staff"].account_id,
        name="Test Client",
        domain="test.com",
        business_type="local",
        locale="en-US",
        package_keywords=10,
        status="active",
        onboarded_at="2026-08-18"
    )
    db_session.add(test_client)
    db_session.commit()
    
    keyword_id = uuid.uuid4()
    kw = Keyword(id=keyword_id, client_id=test_client.id, term="test kw", is_active=True, added_at="2026-08-18")
    db_session.add(kw)
    db_session.commit()
    
    res = client.put(f"/clients/{test_client.id}/keywords/{keyword_id}?is_active=false")
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    res = client.put(f"/clients/{test_client.id}/keywords/{keyword_id}?is_active=true")
    assert res.status_code == 200
    assert res.json()["is_active"] is True
