import logging
import os
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import SessionLocal
from app.models import User
from app.models.account import Account
from app.models.enums import UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def init_db():
    db: Session = SessionLocal()
    try:
        account = db.query(Account).first()
        if not account:
            logger.info("Creating default account")
            account = Account(name="EZ Rankings HQ")
            db.add(account)
            db.commit()
            db.refresh(account)

        # The first super admin comes from the environment, once, on an empty
        # database. Nothing is created without both values — never a default password.
        email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD") or ""
        if db.query(User).filter(User.role == UserRole.super_admin).first():
            logger.info("A super admin already exists.")
        elif not email or len(password) < 10:
            logger.warning("No super admin yet: set ADMIN_EMAIL and ADMIN_PASSWORD (10+ characters) and redeploy.")
        else:
            db.add(User(email=email, password_hash=get_password_hash(password), is_active=True,
                        role=UserRole.super_admin, account_id=account.id))
            db.commit()
            logger.info("Super admin %s created.", email)

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialization finished.")
