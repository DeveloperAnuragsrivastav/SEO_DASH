from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, SyncStatus
from app.models.sync_run import SyncRun
from app.services.dataforseo_auth import get_dataforseo_credentials
from app.services.dataforseo_keyword import fetch_keyword_metrics_with_retry
import datetime

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/keyword-research",
    tags=["keyword_research"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

@router.get("")
def get_keyword_research(
    client_id: uuid.UUID,
    term: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """
    On-demand keyword research lookup via DataForSEO Live API.
    Requires an active DataForSEO connection for the client.
    """
    # Find DataForSEO connection
    conn = db.query(Connection).filter(
        Connection.client_id == client_id,
        Connection.provider == ProviderType.dataforseo,
        Connection.status == ConnectionStatus.connected
    ).first()

    if not conn:
        raise HTTPException(status_code=400, detail="No active DataForSEO connection found for client.")

    try:
        login, password = get_dataforseo_credentials(db, conn.id)
        metrics = fetch_keyword_metrics_with_retry(login, password, term)
        
        # Log successful sync_run
        sync_run = SyncRun(
            client_id=client_id,
            provider="dataforseo",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=SyncStatus.success,
            cost=metrics.get("cost", 0.0)
        )
        db.add(sync_run)
        db.commit()

        return {
            "term": term,
            **metrics
        }
    except Exception as e:
        # Log failed sync_run
        sync_run = SyncRun(
            client_id=client_id,
            provider="dataforseo",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=SyncStatus.failed,
            error=str(e)
        )
        db.add(sync_run)
        db.commit()

        # A 502 Bad Gateway is appropriate for an upstream provider error
        raise HTTPException(status_code=502, detail=f"Failed to fetch keyword data: {str(e)}")
