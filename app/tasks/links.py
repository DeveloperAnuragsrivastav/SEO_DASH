from __future__ import annotations
import logging
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.link import Link
from app.models.enums import LinkStatus
from app.services.links import check_client_links_liveness

logger = logging.getLogger(__name__)

@celery_app.task(name="check_all_links_liveness")
def check_all_links_liveness():
    """
    Runs on the 1st of every month to check liveness for all active links across all clients.
    """
    logger.info("Starting global link liveness check.")
    with SessionLocal() as db:
        try:
            # Find all distinct client_ids that have at least one active link
            client_ids = db.scalars(
                select(Link.client_id)
                .where(Link.status == LinkStatus.active)
                .distinct()
            ).all()

            for client_id in client_ids:
                try:
                    # check_client_links_liveness handles its own sync_run logging per client
                    check_client_links_liveness(db, client_id)
                except Exception as e:
                    logger.error(f"Failed to check link liveness for client {client_id}: {e}")
                    
            logger.info(f"Finished global link liveness check for {len(client_ids)} clients.")
        except Exception as e:
            logger.error(f"Failed to fetch clients for global link liveness check: {e}")
