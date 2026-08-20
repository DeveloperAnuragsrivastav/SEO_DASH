from __future__ import annotations
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.client import Client
from app.models.keyword import Keyword
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, SyncStatus
from app.models.sync_run import SyncRun
from app.schemas.keyword import KeywordCreate, KeywordResponse
from app.services.dataforseo_auth import get_dataforseo_credentials
from app.services.dataforseo_keyword import fetch_keyword_metrics_with_retry

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/keywords",
    tags=["keywords"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

@router.get("", response_model=list[KeywordResponse])
def list_keywords(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """List all active keywords for a client."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    keywords = db.execute(
        select(Keyword)
        .where(Keyword.client_id == client_id)
        .where(Keyword.is_active == True)
        .order_by(Keyword.added_at.desc())
    ).scalars().all()
    
    return list(keywords)


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
def create_keyword(
    client_id: uuid.UUID, keyword_in: KeywordCreate, db: Session = Depends(get_db)
):
    """
    Creates a keyword. Optionally looks up search_volume synchronously if fetch_metrics is True.
    """
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    search_volume = keyword_in.search_volume

    if keyword_in.fetch_metrics and search_volume is None:
        conn = db.query(Connection).filter(
            Connection.client_id == client_id,
            Connection.provider == ProviderType.dataforseo,
            Connection.status == ConnectionStatus.connected
        ).first()

        if conn:
            try:
                login, password = get_dataforseo_credentials(db, conn.id)
                metrics = fetch_keyword_metrics_with_retry(login, password, keyword_in.term)
                search_volume = metrics.get("search_volume")
                
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

                # If fetch_metrics is requested but fails, we should explicitly inform the user.
                raise HTTPException(status_code=502, detail=f"Failed to fetch keyword metrics: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail="Cannot fetch metrics: No active DataForSEO connection.")

    keyword = Keyword(
        client_id=client_id,
        term=keyword_in.term,
        search_volume=search_volume,
        is_active=True,
        added_at=datetime.date.today()
    )
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    
    return keyword

@router.put("/{keyword_id}", response_model=KeywordResponse)
def update_keyword(
    client_id: uuid.UUID, keyword_id: uuid.UUID, is_active: bool, db: Session = Depends(get_db)
):
    """Deactivate or reactivate a keyword."""
    keyword = db.execute(
        select(Keyword).where(Keyword.client_id == client_id, Keyword.id == keyword_id)
    ).scalar_one_or_none()
    
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    keyword.is_active = is_active
    db.commit()
    db.refresh(keyword)
    return keyword
