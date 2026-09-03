import os
from dotenv import load_dotenv

# load .env
load_dotenv("/Users/admin/Desktop/anurag/seo_dahboard/.env")

from app.database import SessionLocal
from app.models.client import Client
from app.tasks.reports import generate_snapshot_report

db = SessionLocal()
client = db.query(Client).first()
if client:
    print(f"Generating snapshot for client {client.name} ({client.id})")
    try:
        generate_snapshot_report(str(client.id))
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED: {e}")
else:
    print("No client found")
db.close()
