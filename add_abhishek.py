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

# Check if user already exists
u = db.query(User).filter_by(email="abhishek@ezrankings.com").first()
if not u:
    u = User(account_id=acc.id, email="abhishek@ezrankings.com", password_hash=get_password_hash("1123"), role=UserRole.agency_admin)
    db.add(u)
    db.commit()
    print("Superadmin added.")
else:
    u.password_hash = get_password_hash("1123")
    u.role = UserRole.agency_admin
    db.commit()
    print("Superadmin updated.")
