from __future__ import annotations
"""Routes for Client management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.enums import ClientStatus, UserRole
from app.dependencies import RequireRole

# Create router for operations that require agency_admin (mutations)
router = APIRouter(
    prefix="/clients",
    tags=["clients"],
)

class ClientCreate(BaseModel):
    name: str
    domain: str
    logo_url: str | None = None
    business_type: str
    locale: str
    package_keywords: int
    status: ClientStatus = ClientStatus.active

class ClientUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    theme_color: str | None = None
    business_type: str | None = None
    locale: str | None = None
    package_keywords: int | None = None
    status: ClientStatus | None = None

class ClientResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    domain: str
    logo_url: str | None
    theme_color: str | None
    business_type: str
    locale: str
    package_keywords: int
    status: ClientStatus
    onboarded_at: datetime

    model_config = {"from_attributes": True}

from app.dependencies import RequireRole, get_current_user
from app.models.user import User

@router.get("", response_model=list[ClientResponse], dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))])
def list_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[Client]:
    """List all clients scoped by role."""
    from app.models.user_project import UserProjectAssignment
    
    if current_user.role == UserRole.super_admin:
        return db.query(Client).all()
        
    if current_user.role == UserRole.manager:
        return db.query(Client).filter(Client.manager_id == current_user.id).all()
        
    if current_user.role == UserRole.user:
        return db.query(Client).join(UserProjectAssignment).filter(
            UserProjectAssignment.user_id == current_user.id
        ).all()
        
    return []


@router.get("/{client_id}", response_model=ClientResponse, dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))])
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    """Get a single client by ID."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=ClientResponse, status_code=201, dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager]))])
def create_client(data: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Client:
    """Create a new client."""
    from app.models.account import Account
    
    # Normally we would derive account_id from the authenticated user.
    # Since we are single-tenant, we fetch the first account.
    account = db.query(Account).first()
    if not account:
        raise HTTPException(status_code=500, detail="System account not configured")
        
    client = Client(
        account_id=account.id,
        manager_id=current_user.id if current_user.role == UserRole.manager else None,
        name=data.name,
        domain=data.domain,
        logo_url=data.logo_url,
        business_type=data.business_type,
        locale=data.locale,
        package_keywords=data.package_keywords,
        status=data.status,
        onboarded_at=datetime.now(timezone.utc).date(),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientResponse, dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))])
def update_client(client_id: uuid.UUID, data: ClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Client:
    """Update an existing client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    if current_user.role == UserRole.manager and client.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this client")
        
    if data.name is not None:
        client.name = data.name
    if data.domain is not None:
        client.domain = data.domain
    if data.logo_url is not None:
        client.logo_url = data.logo_url
    if data.theme_color is not None:
        client.theme_color = data.theme_color
    if data.business_type is not None:
        client.business_type = data.business_type
    if data.locale is not None:
        client.locale = data.locale
    if data.package_keywords is not None:
        client.package_keywords = data.package_keywords
    if data.status is not None:
        client.status = data.status
        
    db.commit()
    db.refresh(client)
    return client

class SectionToggle(BaseModel):
    enabled: bool


class SectionResponse(BaseModel):
    section_key: str
    enabled: bool

    class Config:
        from_attributes = True


@router.get(
    "/{client_id}/sections",
    response_model=list[SectionResponse],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))],
)
def list_client_sections(client_id: uuid.UUID, db: Session = Depends(get_db)) -> list:
    """Per-client section toggles.

    Used to record how a client's traffic data is supplied — e.g. the
    ``ga4_manual`` / ``gsc_manual`` keys mark a source as hand-entered rather
    than pulled through an API connection.
    """
    from app.models.client_section import ClientSection

    return db.query(ClientSection).filter(ClientSection.client_id == client_id).all()


@router.put(
    "/{client_id}/sections/{section_key}",
    response_model=SectionResponse,
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))],
)
def set_client_section(
    client_id: uuid.UUID,
    section_key: str,
    data: SectionToggle,
    db: Session = Depends(get_db),
):
    """Create or update one section toggle for a client."""
    from app.models.client_section import ClientSection

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    row = (
        db.query(ClientSection)
        .filter(
            ClientSection.client_id == client_id,
            ClientSection.section_key == section_key,
        )
        .first()
    )
    if row:
        row.enabled = data.enabled
    else:
        row = ClientSection(client_id=client_id, section_key=section_key, enabled=data.enabled)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(RequireRole([UserRole.super_admin]))])
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a client and all associated data. Restricted to super_admin."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    from app.models.client_section import ClientSection
    from app.models.connection import Connection
    from app.models.keyword import Keyword
    from app.models.ranking import Ranking
    from app.models.ai_prompt import AiPrompt
    from app.models.ai_mention import AiMention
    from app.models.link import Link
    from app.models.activity import Activity
    from app.models.screenshot import Screenshot
    from app.models.report_snapshot import ReportSnapshot
    from app.models.sync_run import SyncRun
    from app.models.user_project import UserProjectAssignment
    from app.models.metric import Metric
    
    # Rankings depend on Keywords
    keyword_ids = [k.id for k in db.query(Keyword.id).filter(Keyword.client_id == client_id).all()]
    from app.models.user import User
    from app.models.user_project import UserProjectAssignment

    # Delete standard users who are ONLY assigned to this client
    assigned_users = db.query(UserProjectAssignment.user_id).filter(UserProjectAssignment.client_id == client_id).all()
    user_ids_to_check = [u[0] for u in assigned_users]
    
    users_to_delete = []
    for uid in user_ids_to_check:
        other_assignments = db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == uid, UserProjectAssignment.client_id != client_id).count()
        if other_assignments == 0:
            users_to_delete.append(uid)
            
    # Also find users where client_id is directly set to this client (Phase 1 legacy)
    legacy_users = db.query(User.id).filter(User.client_id == client_id).all()
    for lu in legacy_users:
        if lu[0] not in users_to_delete:
            users_to_delete.append(lu[0])

    if keyword_ids:
        db.query(Ranking).filter(Ranking.keyword_id.in_(keyword_ids)).delete(synchronize_session=False)
        db.query(Screenshot).filter(Screenshot.keyword_id.in_(keyword_ids)).delete(synchronize_session=False)
        
    db.query(Keyword).filter(Keyword.client_id == client_id).delete(synchronize_session=False)
    
    # Old background-sync tasks hang off the client's connections and sync runs.
    from app.models.provider_task import ProviderTask
    connection_ids = [c.id for c in db.query(Connection.id).filter(Connection.client_id == client_id).all()]
    sync_ids = [r.id for r in db.query(SyncRun.id).filter(SyncRun.client_id == client_id).all()]
    if connection_ids:
        db.query(ProviderTask).filter(ProviderTask.connection_id.in_(connection_ids)).delete(synchronize_session=False)
    if sync_ids:
        db.query(ProviderTask).filter(ProviderTask.sync_run_id.in_(sync_ids)).delete(synchronize_session=False)

    # Delete everything else that has client_id
    for model in [ClientSection, Connection, AiMention, AiPrompt, Link, Activity, Screenshot, ReportSnapshot, SyncRun, UserProjectAssignment, Metric]:
        db.query(model).filter(model.client_id == client_id).delete(synchronize_session=False)
        
    if users_to_delete:
        db.query(User).filter(User.id.in_(users_to_delete)).delete(synchronize_session=False)
        
    db.delete(client)
    db.commit()
    return None
