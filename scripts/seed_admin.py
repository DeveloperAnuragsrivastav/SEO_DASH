from __future__ import annotations
import os
import sys
import getpass
from sqlalchemy.orm import Session
from app.database import engine, Base
from app.models.user import User
from app.models.account import Account
from app.models.enums import UserRole
import passlib.context

pwd_context = passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    email = input("Enter admin email: ").strip()
    if not email:
        print("Email cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Enter admin password: ")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)
        
    password_hash = pwd_context.hash(password)

    with Session(engine) as session:
        # Check if user exists
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            print(f"User {email} already exists.")
            sys.exit(0)
            
        # Get or create default account
        account = session.query(Account).first()
        if not account:
            print("No account found. Creating a default account...")
            account = Account(name="Default Agency Account")
            session.add(account)
            session.flush()

        user = User(
            account_id=account.id,
            email=email,
            password_hash=password_hash,
            role=UserRole.agency_admin
        )
        session.add(user)
        session.commit()
        print(f"Successfully created agency_admin user: {email}")

if __name__ == "__main__":
    main()
