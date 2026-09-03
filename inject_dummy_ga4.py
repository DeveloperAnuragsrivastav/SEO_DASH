import datetime
import random
from sqlalchemy import text
from app.database import SessionLocal
from app.models.metric import Metric
from app.models.enums import MetricSource

db = SessionLocal()

# Get all clients
clients = db.execute(text("SELECT id FROM clients")).fetchall()
client_ids = [c[0] for c in clients]

dates = [
    datetime.date(2026, 6, 1),
    datetime.date(2026, 7, 1),
    datetime.date(2026, 8, 1)
]

metrics_to_insert = []

for cid in client_ids:
    for d in dates:
        # Totals
        sessions = random.randint(1000, 5000)
        users = int(sessions * random.uniform(0.7, 0.9))
        engaged = int(sessions * random.uniform(0.4, 0.6))
        conv = random.randint(10, 100)
        
        totals = {
            "sessions": sessions,
            "users": users,
            "engaged_sessions": engaged,
            "conversions": conv
        }
        
        for k, v in totals.items():
            metrics_to_insert.append(Metric(
                client_id=cid,
                provider="ga4",
                metric_key=k,
                dimension_key=None,
                dimension_value=None,
                captured_on=d,
                value=v,
                source=MetricSource.api
            ))
            
        # Channels
        for channel in ["Organic Search", "Direct", "Paid Search"]:
            metrics_to_insert.append(Metric(
                client_id=cid,
                provider="ga4",
                metric_key="sessions",
                dimension_key="channel",
                dimension_value=channel,
                captured_on=d,
                value=int(sessions * random.uniform(0.2, 0.4)),
                source=MetricSource.api
            ))
            
        # Devices
        for device in ["desktop", "mobile"]:
            metrics_to_insert.append(Metric(
                client_id=cid,
                provider="ga4",
                metric_key="sessions",
                dimension_key="deviceCategory",
                dimension_value=device,
                captured_on=d,
                value=int(sessions * random.uniform(0.4, 0.6)),
                source=MetricSource.api
            ))
            
        # Countries
        for country in ["United States", "India", "United Kingdom"]:
            metrics_to_insert.append(Metric(
                client_id=cid,
                provider="ga4",
                metric_key="sessions",
                dimension_key="country",
                dimension_value=country,
                captured_on=d,
                value=int(sessions * random.uniform(0.1, 0.3)),
                source=MetricSource.api
            ))

# Delete existing GA4 data for these dates so we don't duplicate
for d in dates:
    db.execute(text("DELETE FROM metrics WHERE provider='ga4' AND captured_on=:d"), {"d": d})

db.add_all(metrics_to_insert)
db.commit()

print(f"Inserted {len(metrics_to_insert)} GA4 metrics for {len(client_ids)} clients.")
