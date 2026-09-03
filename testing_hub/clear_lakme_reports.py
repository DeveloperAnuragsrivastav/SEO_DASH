from app.database import SessionLocal
from app.models.client import Client
from app.models.report_snapshot import ReportSnapshot

db = SessionLocal()
client = db.query(Client).filter(Client.name.ilike('%lakme%')).first()
if client:
    deleted = db.query(ReportSnapshot).filter(ReportSnapshot.client_id == client.id).delete()
    db.commit()
    print(f"Deleted {deleted} reports for client {client.name}")
else:
    print("Client not found")
