from __future__ import annotations
import datetime
import logging
import uuid
from typing import Any
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, text
from calendar import monthrange

from app.celery_app import celery_app
from app.database import SessionLocal, engine
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, ReportStatus
from app.models.report_snapshot import ReportSnapshot
from app.services.ga4_service import pull_ga4_data
from app.services.gbp_service import pull_gbp_data
from app.services.openai_service import generate_report_narrative
from app.services.report_period import build_report_data
from app.services.gsc_service import pull_gsc_data
from app.routes.reports import _resolve_metrics, _resolve_rankings, _resolve_ai_visibility, _resolve_links, _resolve_activities, _resolve_screenshots, _compute_kpi_deltas, get_month_boundaries

logger = logging.getLogger(__name__)

@celery_app.task(name="generate_snapshot_report", bind=True, max_retries=3)
def generate_snapshot_report(self, client_id_str: str, months: int = 1):
    """
    Background task to generate the rolling 30-day SEO report asynchronously.
    """
    client_id = uuid.UUID(client_id_str)
    end_date = datetime.date.today() - datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=29)
    
    lock_id = hash(f"{client_id}-{end_date.strftime('%Y-%m-%d')}") & 0x7FFFFFFFFFFFFFFF
    
    with engine.connect() as lock_conn:
        acquired = lock_conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
        if not acquired:
            logger.warning(f"Report generation already in progress for {client_id} {end_date}")
            return "Already in progress"
            
        db = SessionLocal()
        try:
            client = db.get(Client, client_id)
            if not client:
                logger.error("Client not found.")
                return "Client not found"
                
            existing = db.execute(
                select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.end_date == end_date)
            ).scalars().first()
            
            if existing:
                if existing.status == ReportStatus.published:
                    logger.info("Report is published and cannot be overwritten.")
                    return "Report is published"
                logger.info("Overwriting existing draft report snapshot.")

            prev_end = start_date - datetime.timedelta(days=1)
            prev_start = prev_end - datetime.timedelta(days=30)

            # 2. Data Resolution (Live Pulls)
            connections = db.execute(
                select(Connection).where(Connection.client_id == client_id)
            ).scalars().all()
            
            gsc_live_data = None
            ga4_live_data = None
            
            for conn in connections:
                if conn.status == ConnectionStatus.connected:
                    try:
                        if conn.provider == ProviderType.gsc:
                            gsc_live_data = pull_gsc_data(db, conn.id, start_date, end_date)
                        elif conn.provider == ProviderType.ga4:
                            ga4_live_data = pull_ga4_data(db, conn.id, start_date, end_date)
                        elif conn.provider == ProviderType.gbp:
                            pull_gbp_data(db, conn.id, start_date, end_date)
                    except Exception as e:
                        logger.error(f"Live pull failed for {conn.provider.value}: {e}")

            # The current cycle as Google gave it, for the sources that are connected.
            live = {}
            if gsc_live_data:
                live["gsc"] = {**gsc_live_data["totals"], "top_pages": gsc_live_data["top_pages"]}
            if ga4_live_data:
                live["ga4"] = {
                    **ga4_live_data["totals"],
                    "traffic_sources": ga4_live_data["traffic_sources"],
                    "devices": ga4_live_data["devices"],
                    "top_pages": ga4_live_data["top_pages"],
                    "countries": ga4_live_data.get("countries", []),
                }

            # Older cycles are read from what is already stored — only the
            # current cycle was pulled above.
            snapshot: dict[str, Any] = build_report_data(db, client_id, end_date, months, live=live)
            window_start = datetime.date.fromisoformat(snapshot["period"]["start"])

            # 3. Narrative Auto-Draft
            try:
                date_range_label = f"{window_start.strftime('%B %d')} to {end_date.strftime('%B %d, %Y')}"
                narrative = generate_report_narrative(client.name, date_range_label, snapshot)
            except Exception as e:
                logger.error(f"Groq narrative generation failed: {e}")
                narrative = "Narrative auto-generation failed. Please draft manually."

            # 4. Write Report
            if existing:
                # Regenerating a draft keeps what the person already chose.
                for keep in ("included_sections", "included_items", "copy"):
                    if keep in (existing.snapshot or {}):
                        snapshot[keep] = existing.snapshot[keep]
                existing.start_date = window_start
                existing.snapshot = snapshot
                if not existing.narrative or existing.narrative == "Narrative auto-generation failed. Please draft manually.":
                    existing.narrative = narrative
                existing.generated_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                return str(existing.id)
            else:
                report = ReportSnapshot(
                    client_id=client_id,
                    start_date=window_start,
                    end_date=end_date,
                    status=ReportStatus.draft,
                    snapshot=snapshot,
                    narrative=narrative,
                    generated_at=datetime.datetime.now(datetime.timezone.utc),
                )
                db.add(report)
                db.commit()
                return str(report.id)
            
            return str(report.id)
            
        except Exception as e:
            logger.exception("Task failed.")
            db.rollback()
            raise self.retry(exc=e, countdown=60)
        finally:
            db.close()
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
