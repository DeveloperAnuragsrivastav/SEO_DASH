from __future__ import annotations
from app.database import SessionLocal
from app.models.client import Client
from app.models.link import Link
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from sqlalchemy import select, delete, func

def reset_and_seed():
    db = SessionLocal()
    try:
        from app.models.enums import ClientStatus
        client = db.execute(select(Client).where(Client.status == ClientStatus.active)).scalars().first()
        if not client:
            print("No active client found.")
            return

        print(f"--- Client ID: {client.id} ---")
        
        # 1. Fully clear the links and activities (and screenshots just in case) for this client
        print("\n1. Clearing tables for client...")
        db.execute(delete(Link).where(Link.client_id == client.id))
        db.execute(delete(Activity).where(Activity.client_id == client.id))
        # Also clean up screenshots from the seed to ensure full reset
        db.execute(delete(Screenshot).where(Screenshot.client_id == client.id))
        db.commit()
        
        # Verify clear
        links_zero = db.execute(select(func.count(Link.id)).where(Link.client_id == client.id)).scalar()
        acts_zero = db.execute(select(func.count(Activity.id)).where(Activity.client_id == client.id)).scalar()
        print(f"Verification -> Links: {links_zero}, Activities: {acts_zero}")
        
    except Exception as e:
        db.rollback()
        print(f"Error during reset: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed()
