import pytest
from app.services.ga4_service import get_ai_referrals
from app.database import get_db
import uuid
from datetime import date, timedelta
import os

@pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="Needs live GA4 credentials")
def test_live_get_ai_referrals():
    client_id = uuid.UUID("6d64979f-abb8-45e4-a9f5-4ab1fac4508f")
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # We must use the REAL database, so we change DATABASE_URL to the real db in this test
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@postgres:5432/ez_rankings"
    
    # get a session to the real DB
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(os.environ["DATABASE_URL"])
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        results = get_ai_referrals(db, client_id, start_date, end_date)
        print(f"\nLIVE GA4 AI REFERRALS FETCHED: {results}")
        assert isinstance(results, list)
    finally:
        db.close()
