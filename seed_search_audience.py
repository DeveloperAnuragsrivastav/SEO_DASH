from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
import datetime

from app.models.client import Client
from app.models.metric import Metric
from app.models.enums import MetricSource

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/seo_dashboard")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Target client
client_id = uuid.UUID('22aa3418-4c06-4bf5-8c12-e7ea9135e850')
client = db.get(Client, client_id)

if not client:
    print("Client not found")
    exit(1)

target_month = datetime.date(2026, 8, 1)
prev_month = datetime.date(2026, 7, 1)

# Clear old metrics for these tests
db.query(Metric).filter(
    Metric.client_id == client_id,
    Metric.dimension_key.in_(["page", "channel", "device", "country"])
).delete()

metrics_to_insert = []

# --- GSC Search Performance Data ---
# Page 1: Trending Up
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="clicks", dimension_key="page", dimension_value="/blog/seo-tips", value=150, captured_on=prev_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="clicks", dimension_key="page", dimension_value="/blog/seo-tips", value=250, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="impressions", dimension_key="page", dimension_value="/blog/seo-tips", value=5000, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="ctr", dimension_key="page", dimension_value="/blog/seo-tips", value=0.05, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="position", dimension_key="page", dimension_value="/blog/seo-tips", value=4.5, captured_on=target_month, source=MetricSource.api))

# Page 2: Trending Down
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="clicks", dimension_key="page", dimension_value="/pricing", value=300, captured_on=prev_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="clicks", dimension_key="page", dimension_value="/pricing", value=100, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="impressions", dimension_key="page", dimension_value="/pricing", value=2000, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="ctr", dimension_key="page", dimension_value="/pricing", value=0.05, captured_on=target_month, source=MetricSource.api))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="position", dimension_key="page", dimension_value="/pricing", value=12.2, captured_on=target_month, source=MetricSource.api))

# Page 3: New
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="clicks", dimension_key="page", dimension_value="/features/new-launch", value=400, captured_on=target_month, source=MetricSource.manual))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="impressions", dimension_key="page", dimension_value="/features/new-launch", value=8000, captured_on=target_month, source=MetricSource.manual))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="ctr", dimension_key="page", dimension_value="/features/new-launch", value=0.05, captured_on=target_month, source=MetricSource.manual))
metrics_to_insert.append(Metric(client_id=client_id, provider="gsc", metric_key="position", dimension_key="page", dimension_value="/features/new-launch", value=3.1, captured_on=target_month, source=MetricSource.manual))

# --- GA4 Audience Data ---
ga4_data = [
    # Channel
    ("channel", "Organic Search", 1200, 1000, 800, 50, 1000.00, MetricSource.api),
    ("channel", "Direct", 800, 750, 500, 20, 400.00, MetricSource.api),
    ("channel", "Referral", 300, 280, 200, 5, 50.00, MetricSource.manual),
    # Device
    ("device", "Mobile", 1500, 1400, 900, 30, 600.00, MetricSource.api),
    ("device", "Desktop", 700, 600, 500, 40, 800.00, MetricSource.api),
    ("device", "Tablet", 100, 90, 80, 5, 50.00, MetricSource.api),
    # Country
    ("country", "United States", 1800, 1600, 1200, 65, 1200.00, MetricSource.api),
    ("country", "United Kingdom", 300, 280, 200, 8, 200.00, MetricSource.api),
    ("country", "Canada", 200, 180, 100, 2, 50.00, MetricSource.api),
]

for dim_key, dim_val, sess, usr, eng, conv, rev, src in ga4_data:
    metrics_to_insert.extend([
        Metric(client_id=client_id, provider="ga4", metric_key="sessions", dimension_key=dim_key, dimension_value=dim_val, value=sess, captured_on=target_month, source=src),
        Metric(client_id=client_id, provider="ga4", metric_key="users", dimension_key=dim_key, dimension_value=dim_val, value=usr, captured_on=target_month, source=src),
        Metric(client_id=client_id, provider="ga4", metric_key="engaged_sessions", dimension_key=dim_key, dimension_value=dim_val, value=eng, captured_on=target_month, source=src),
        Metric(client_id=client_id, provider="ga4", metric_key="conversions", dimension_key=dim_key, dimension_value=dim_val, value=conv, captured_on=target_month, source=src),
        Metric(client_id=client_id, provider="ga4", metric_key="revenue", dimension_key=dim_key, dimension_value=dim_val, value=rev, captured_on=target_month, source=src)
    ])

db.add_all(metrics_to_insert)
db.commit()

print("Successfully seeded search performance and audience data")
