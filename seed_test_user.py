from __future__ import annotations
from app.database import SessionLocal
from app.models.user import User
from app.models.account import Account
from app.models.enums import UserRole
from app.core.security import get_password_hash

db = SessionLocal()
acc = db.query(Account).first()
if not acc:
    acc = Account(name="Test Account")
    db.add(acc)
    db.commit()

u = User(account_id=acc.id, email="admin@ezrankings.com", password_hash=get_password_hash("password123"), role=UserRole.agency_admin)
db.add(u)
db.commit()
print("User seeded.")
