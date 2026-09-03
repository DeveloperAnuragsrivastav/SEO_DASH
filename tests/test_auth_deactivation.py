import pytest
from app.models.user import User
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user

client = TestClient(app)

def test_mid_session_deactivation(test_users, db_session, admin_auth_headers):
    from app.dependencies import get_db
    admin_user = test_users["admin"]
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    
    # First, confirm the token works
    res1 = client.get("/auth/me", headers=admin_auth_headers)
    assert res1.status_code == 200

    # Now, explicitly deactivate the user mid-session
    user = db_session.execute(select(User).where(User.id == admin_user.id)).scalar_one_or_none()
    assert user is not None
    user.is_active = False
    db_session.commit()

    # The token is still cryptographically valid, but get_current_user should now reject it
    res2 = client.get("/auth/me", headers=admin_auth_headers)
    assert res2.status_code == 401
    assert "Inactive user" in res2.json()["detail"]
