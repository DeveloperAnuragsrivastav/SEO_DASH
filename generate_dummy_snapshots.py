import uuid
import datetime
from sqlalchemy import text
from app.database import SessionLocal
from app.models.report_snapshot import ReportSnapshot

db = SessionLocal()

client_id = uuid.UUID('8b41e88a-aa45-4647-94f7-d4e9ff0cf5b6')

# Delete existing dummy snapshots if any to avoid duplication
db.execute(text("DELETE FROM report_snapshots WHERE client_id = :cid AND start_date < '2026-07-27'"), {"cid": client_id})

# Generate snapshot for June
snap_june = ReportSnapshot(
    client_id=client_id,
    start_date=datetime.date(2026, 5, 27),
    end_date=datetime.date(2026, 6, 26),
    snapshot={"dummy": True},
    narrative="Dummy narrative for June",
    status="draft",
    generated_at=datetime.datetime.now(datetime.timezone.utc)
)

# Generate snapshot for July
snap_july = ReportSnapshot(
    client_id=client_id,
    start_date=datetime.date(2026, 6, 27),
    end_date=datetime.date(2026, 7, 26),
    snapshot={"dummy": True},
    narrative="Dummy narrative for July",
    status="draft",
    generated_at=datetime.datetime.now(datetime.timezone.utc)
)

db.add(snap_june)
db.add(snap_july)
db.commit()

print("Inserted dummy snapshots for June and July.")
