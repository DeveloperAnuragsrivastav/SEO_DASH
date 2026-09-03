import sys
import os
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@postgres:5432/ez_rankings"
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.models.enums import UserRole
from app.models.user_project import UserProjectAssignment

engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine)
db = Session()

# Find standard users with 0 assignments
standard_users = db.query(User).filter(User.role == UserRole.user).all()
deleted_count = 0
for u in standard_users:
    count = db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == u.id).count()
    if count == 0 and u.client_id is None:
        print(f"Deleting orphaned user: {u.email}")
        db.delete(u)
        deleted_count += 1

db.commit()
print(f"Deleted {deleted_count} orphaned users.")
