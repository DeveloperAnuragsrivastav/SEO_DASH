from __future__ import annotations
from app.database import SessionLocal
from app.models.client import Client
from app.models.link import Link
from app.models.activity import Activity
from sqlalchemy import select, func

def count_data():
    db = SessionLocal()
    try:
        from app.models.enums import ClientStatus
        client = db.execute(select(Client).where(Client.status == ClientStatus.active)).scalars().first()
        if not client:
            print("No active client found.")
            return

        print(f"\n3. Querying COUNT(*) for client {client.id}")
        
        links_count = db.execute(select(func.count(Link.id)).where(Link.client_id == client.id)).scalar()
        acts_count = db.execute(select(func.count(Activity.id)).where(Activity.client_id == client.id)).scalar()
        
        print(f"RAW OUTPUT -> Links: {links_count}")
        print(f"RAW OUTPUT -> Activities: {acts_count}")
        
    except Exception as e:
        print(f"Error during count: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    count_data()
