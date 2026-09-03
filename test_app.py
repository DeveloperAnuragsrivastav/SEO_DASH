import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.getcwd())
from app.main import app

client = TestClient(app)

# We can bypass auth by overriding the dependency
from app.dependencies import get_current_user
from app.models.user import User
from app.models.enums import UserRole
import uuid

def override_get_current_user():
    return User(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=UserRole.agency_admin,
        is_active=True
    )

app.dependency_overrides[get_current_user] = override_get_current_user

res = client.get("/clients")
print("CLIENTS STATUS:", res.status_code)
print("CLIENTS BODY:", res.json())

res2 = client.get("/users")
print("USERS STATUS:", res2.status_code)
print("USERS BODY:", res2.json())

