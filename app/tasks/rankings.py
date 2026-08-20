from __future__ import annotations
import logging
from datetime import date, datetime, timedelta, timezone.utc

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import ClientStatus, ConnectionStatus, ProviderType, SyncStatus, TaskStatus
from app.models.keyword import Keyword
from app.models.provider_task import ProviderTask
from app.models.sync_run import SyncRun
from app.services.dataforseo_auth import _post_serp_tasks_with_retry, get_dataforseo_credentials

logger = logging.getLogger(__name__)


def _batch_keywords(keywords, batch_size=100):
    for i in range(0, len(keywords), batch_size):
        yield keywords[i : i + batch_size]


@celery_app.task(name="test_celery_task")
def test_celery_task():
    """A trivial dummy task to verify Celery worker and beat are configured correctly."""
    logger.info("Executing dummy test_celery_task.")
    print("Executing dummy test_celery_task (stdout).")
    return "Dummy task successful"


@celery_app.task(name="trigger_nightly_rankings_pull")
def trigger_nightly_rankings_pull():
    """Triggered by Celery Beat to fetch rankings for all active DataForSEO connections."""
    with SessionLocal() as db:
        from app.models.cost import ProviderState
        
        provider_state = db.execute(
            select(ProviderState).where(ProviderState.provider == "dataforseo")
        ).scalar_one_or_none()
        
        if provider_state and provider_state.is_paused:
            logger.error("Rankings job aborted: Provider 'dataforseo' is PAUSED due to cost guardrail.")
            return

        stmt = (
            select(Connection)
            .join(Client)
            .where(
                Connection.provider == ProviderType.dataforseo,
                Connection.status == ConnectionStatus.connected,
                Client.status == ClientStatus.active
            )
        )
        connections = db.execute(stmt).scalars().all()
        for conn in connections:
            try:
                _process_connection(db, conn)
            except Exception as e:
                logger.error(f"Failed to process rankings for connection {conn.id}: {e}")


def _process_connection(db: Session, conn: Connection):
    today = date.today()
    
    sync_run = SyncRun(
        client_id=conn.client_id,
        provider="dataforseo_serp",
        started_at=datetime.now(timezone.utc),
        status=SyncStatus.partial,
        rows=0,
    )
    db.add(sync_run)
    db.commit()

    try:
        login, password = get_dataforseo_credentials(db, conn.id)
        
        keywords = db.execute(
            select(Keyword)
            .where(Keyword.client_id == conn.client_id, Keyword.is_active == True)
        ).scalars().all()
        
        if not keywords:
            sync_run.status = SyncStatus.success
            sync_run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        total_submitted = 0
        for keyword_batch in _batch_keywords(keywords, 100):
            payload = []
            for kw in keyword_batch:
                tag = f"{conn.client_id}:{kw.id}:{today.isoformat()}"
                
                postback_url = f"{settings.webhook_base_url}/api/webhooks/dataforseo/serp"
                
                payload.append({
                    "keyword": kw.term,
                    "location_code": 2840, # Default to US
                    "language_code": "en",
                    "load_async_ai_overview": True,
                    "tag": tag,
                    "postback_url": postback_url,
                })

            # Send batch with 3x retry
            tasks_response = _post_serp_tasks_with_retry(login, password, payload)
            
            # Immediately synchronously write provider_tasks
            for task_data in tasks_response:
                task_id = task_data.get("id")
                # DataForSEO includes the submitted tag in data.tag
                tag_returned = task_data.get("data", {}).get("tag")
                if not task_id or not tag_returned:
                    continue
                
                ptask = ProviderTask(
                    connection_id=conn.id,
                    task_id=task_id,
                    tag=tag_returned,
                    status=TaskStatus.pending,
                    submitted_at=datetime.now(timezone.utc),
                    sync_run_id=sync_run.id
                )
                db.add(ptask)
                total_submitted += 1
            
            db.commit()

        # Update rows but leave status as partial.
        # It will be marked success by the reconcile_sync_runs task when all webhooks complete.
        sync_run.rows = total_submitted
        db.commit()

    except Exception as e:
        conn.status = ConnectionStatus.error
        conn.last_error = f"SERP pull failed: {str(e)}"
        
        sync_run.status = SyncStatus.failed
        sync_run.error = str(e)
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise e


from app.utils.alerting import send_email_alert

def alert_agency(connection_id, message):
    """
    Actual alerting mechanism calling SMTP fallback. (Architecture.md §13)
    """
    subject = f"Alert for connection {connection_id}"
    try:
        with SessionLocal() as db:
            conn = db.get(Connection, connection_id)
            if conn and conn.client:
                provider_str = conn.provider.value if hasattr(conn.provider, 'value') else str(conn.provider)
                subject = f"[Alert] Provider '{provider_str}' failure for Client '{conn.client.name}'"
    except Exception as e:
        logger.error(f"Error formulating subject in alert_agency: {e}")
        
    send_email_alert(subject, message)


@celery_app.task(name="reconcile_sync_runs")
def reconcile_sync_runs():
    """
    Periodic task (hourly) to reconcile DataForSEO sync runs.
    Checks all sync_runs in 'partial' status.
    - If all linked provider_tasks are 'completed', marks sync_run as 'success'.
    - If any task is 'pending' and older than 120 minutes, marks it as 'failed' and alerts.
    - If all tasks are resolved but some failed, marks sync_run as 'partial' (per spec).
    - If all tasks failed, marks sync_run as 'failed'.
    """
    # Staleness threshold is 120 minutes (2 hours).
    # DataForSEO's Standard method has an average turnaround of 5 minutes (Normal Priority),
    # but their target turnaround is 45 minutes, with potential extensions during high load.
    # Source: DataForSEO SERP API Documentation (Live vs Standard methods).
    # A 120-minute threshold gives a generous margin to prevent false alarms. (Architecture.md §5)
    staleness_threshold = datetime.now(timezone.utc) - timedelta(minutes=120)

    with SessionLocal() as db:
        partial_runs = db.execute(
            select(SyncRun).where(SyncRun.status == SyncStatus.partial)
        ).scalars().all()

        for run in partial_runs:
            tasks = db.execute(
                select(ProviderTask).where(ProviderTask.sync_run_id == run.id)
            ).scalars().all()

            if not tasks:
                # No tasks generated? Mark success.
                run.status = SyncStatus.success
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
                continue

            all_resolved = True
            any_failed = False
            all_failed = True

            for ptask in tasks:
                if ptask.status == TaskStatus.pending:
                    if ptask.submitted_at < staleness_threshold:
                        # Stale! Mark task as failed
                        ptask.status = TaskStatus.failed
                        ptask.completed_at = datetime.now(timezone.utc)
                        
                        # Trigger alert on connection
                        conn = db.execute(
                            select(Connection).where(Connection.id == ptask.connection_id)
                        ).scalar_one()
                        
                        error_msg = f"DataForSEO task {ptask.task_id} stalled and timed out after 120 minutes."
                        conn.status = ConnectionStatus.error
                        conn.last_error = error_msg
                        
                        alert_agency(conn.id, error_msg)
                        
                        any_failed = True
                    else:
                        all_resolved = False
                        all_failed = False
                elif ptask.status == TaskStatus.failed:
                    any_failed = True
                elif ptask.status == TaskStatus.completed:
                    all_failed = False

            if all_resolved:
                run.finished_at = datetime.now(timezone.utc)
                if all_failed:
                    run.status = SyncStatus.failed
                    run.error = "All provider tasks failed."
                elif any_failed:
                    run.status = SyncStatus.partial
                else:
                    run.status = SyncStatus.success
            db.commit()
