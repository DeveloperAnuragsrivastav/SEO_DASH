from __future__ import annotations
import os
import uuid
import random
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.client import Client
from app.models.keyword import Keyword
from app.models.ranking import Ranking
from app.models.screenshot import Screenshot
from app.models.enums import RankingSource

DB_URI = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/seo_dashboard")
engine = create_engine(DB_URI)
SessionLocal = sessionmaker(bind=engine)

def seed_rankings():
    db = SessionLocal()
    client = db.query(Client).first()
    if not client:
        print("No clients found in DB")
        return

    # Delete existing rankings and keywords to start fresh for this script
    db.query(Screenshot).filter_by(client_id=client.id).delete()
    keywords = db.query(Keyword).filter_by(client_id=client.id).all()
    kw_ids = [kw.id for kw in keywords]
    if kw_ids:
        db.query(Ranking).filter(Ranking.keyword_id.in_(kw_ids)).delete()
        db.query(Keyword).filter(Keyword.client_id == client.id).delete()

    # Create 5 keywords
    terms = ["best seo software", "marketing agency nyc", "buy sneakers online", "local plumber", "dentist near me"]
    new_keywords = []
    for term in terms:
        kw = Keyword(client_id=client.id, term=term, added_at=date(2026, 1, 1))
        db.add(kw)
        new_keywords.append(kw)
    db.commit()

    # Base target date
    target_date = date(2026, 8, 31) # End of August
    history_start = target_date - timedelta(days=90)

    # Generate 90 days of daily positions for each keyword
    for i, kw in enumerate(new_keywords):
        current_date = history_start
        # Give them different trends
        # 1. Steady improvement
        # 2. Dropped recently
        # 3. Stable page 1
        # 4. Volatile page 2
        # 5. Out of top 100
        
        pos = 50 if i == 0 else 10 if i == 1 else 3 if i == 2 else 15 if i == 3 else None
        
        while current_date <= target_date:
            source = RankingSource.api
            
            # Trend logic
            if i == 0:
                # Steady improvement
                if current_date.day % 5 == 0:
                    pos = max(1, pos - 1)
            elif i == 1:
                # Dropped recently
                if current_date > target_date - timedelta(days=10):
                    pos = min(100, pos + 5)
            elif i == 2:
                # Stable top 3, manual source on the very last day to show the badge
                if current_date == target_date:
                    source = RankingSource.manual
            elif i == 3:
                # Volatile page 2 (11-20)
                pos = random.randint(11, 20)
            elif i == 4:
                # Out of top 100 for a while, then enters
                if current_date > target_date - timedelta(days=20):
                    pos = random.randint(80, 95)
                else:
                    pos = None
                    
            db.add(Ranking(
                keyword_id=kw.id,
                captured_on=current_date,
                position=pos,
                source=source,
            ))
            current_date += timedelta(days=1)
            
        # Add a screenshot for the first and third keyword for August
        if i in [0, 2]:
            db.add(Screenshot(
                client_id=client.id,
                month=date(2026, 8, 1),
                keyword_id=kw.id,
                file_url="https://via.placeholder.com/600x400.png?text=SERP+Screenshot",
                caption="SERP Snapshot"
            ))

    db.commit()
    print("Seeded 90-day rankings data and screenshots!")

if __name__ == "__main__":
    seed_rankings()
