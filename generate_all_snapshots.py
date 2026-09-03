import datetime
from sqlalchemy import text
from app.database import SessionLocal
from app.models.report_snapshot import ReportSnapshot

db = SessionLocal()

# Get all clients
clients = db.execute(text("SELECT id FROM clients")).fetchall()
client_ids = [c[0] for c in clients]

snaps = []
for cid in client_ids:
    # Delete existing dummy snapshots if any to avoid duplication
    db.execute(text("DELETE FROM report_snapshots WHERE client_id = :cid AND start_date < '2026-07-27'"), {"cid": cid})

    # Generate snapshot for June
    snap_june = ReportSnapshot(
        client_id=cid,
        start_date=datetime.date(2026, 5, 27),
        end_date=datetime.date(2026, 6, 26),
        snapshot={"dummy": True},
        narrative="Dummy narrative for June",
        status="published",
        generated_at=datetime.datetime.now(datetime.timezone.utc)
    )

    # Generate snapshot for July
    snap_july = ReportSnapshot(
        client_id=cid,
        start_date=datetime.date(2026, 6, 27),
        end_date=datetime.date(2026, 7, 26),
        snapshot={"dummy": True},
        narrative="Dummy narrative for July",
        status="published",
        generated_at=datetime.datetime.now(datetime.timezone.utc)
    )
    snaps.append(snap_june)
    snaps.append(snap_july)

db.add_all(snaps)
db.commit()

print(f"Inserted dummy snapshots for {len(client_ids)} clients.")
