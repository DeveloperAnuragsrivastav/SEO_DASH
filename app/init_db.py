import logging
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import SessionLocal
from app.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def init_db():
    db: Session = SessionLocal()
    try:
        email = "rajiv@ezrankings.com"
        admin = db.query(User).filter(User.email == email).first()
        
        if not admin:
            logger.info(f"Creating super admin: {email}")
            admin = User(
                email=email,
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=True,
                full_name="Rajiv Admin"
            )
            db.add(admin)
            db.commit()
            logger.info("Super admin created successfully.")
        else:
            logger.info("Super admin already exists.")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialization finished.")
