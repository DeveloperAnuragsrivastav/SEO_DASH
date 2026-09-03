import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.models.report import ReportSnapshot

engine = create_engine('postgresql://postgres:postgres@localhost:5432/seo_dashboard')
Session = sessionmaker(bind=engine)
db = Session()
client_id = uuid.UUID('f3e327e6-909e-4922-8bbc-552ac6edb9c0')

report = db.execute(
    select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
).scalar_one_or_none()

if not report:
    print("No report")
else:
    print(f"Found report {report.id}")
    print("Snapshot keys:", list(report.snapshot.keys()))
    try:
        import json
        json.dumps(report.snapshot)
        print("JSON dumps OK")
    except Exception as e:
        print("JSON Error:", e)

