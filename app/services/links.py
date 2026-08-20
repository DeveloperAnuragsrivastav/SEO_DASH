from __future__ import annotations
import logging
from datetime import datetime, timezone.utc
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.link import Link
from app.models.enums import LinkStatus, SyncStatus
from app.models.sync_run import SyncRun

logger = logging.getLogger(__name__)

# Retry up to 3 times on typical transient network errors
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    reraise=True
)
def _check_url_liveness(url: str) -> bool:
    """
    Checks if a URL is alive.
    Attempts HEAD first. If 405 Method Not Allowed, falls back to GET.
    Returns True if 2xx, False if 4xx/5xx.
    Raises exceptions for transient network errors to trigger retry.
    """
    # Follow redirects, wait up to 10s
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        response = client.head(url)
        if response.status_code == 405:
            response = client.get(url)
            
        # Consider 200-299 as alive
        if 200 <= response.status_code < 300:
            return True
            
        # Consider 400-599 as dead
        if response.status_code >= 400:
            return False
            
        return True # Catch-all for 3xx if not followed (should be followed), or 1xx

def check_client_links_liveness(db: Session, client_id: str):
    """
    Checks liveness of all active links for a client.
    Updates last_checked and status (to 'removed' if dead).
    Logs the run in sync_runs.
    """
    logger.info(f"Starting link liveness check for client {client_id}")
    
    sync_run = SyncRun(
        client_id=client_id,
        provider="links_liveness",
        started_at=datetime.now(timezone.utc),
        status=SyncStatus.partial
    )
    db.add(sync_run)
    db.commit()
    
    try:
        links = db.scalars(
            select(Link).where(Link.client_id == client_id, Link.status == LinkStatus.active)
        ).all()
        
        checked_count = 0
        dead_count = 0
        
        for link in links:
            try:
                is_alive = _check_url_liveness(link.url)
            except Exception as e:
                logger.warning(f"URL check failed after retries for {link.url}: {e}")
                is_alive = False
                
            link.last_checked = datetime.now(timezone.utc)
            if not is_alive:
                link.status = LinkStatus.removed
                dead_count += 1
                
            checked_count += 1
            
        sync_run.status = SyncStatus.success
        sync_run.rows = checked_count
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Finished link liveness check for client {client_id}. Checked: {checked_count}, Dead: {dead_count}")
        
    except Exception as e:
        logger.error(f"Error during link liveness check for client {client_id}: {e}")
        sync_run.status = SyncStatus.failed
        sync_run.error = str(e)
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise e
