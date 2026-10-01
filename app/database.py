from __future__ import annotations
"""SQLAlchemy engine, session factory, and declarative base."""



from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# A handful of people use this at once, so a small pool is plenty; connections
# are recycled before a hosted Postgres would drop them for idling.
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session, closes on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
