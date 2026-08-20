from __future__ import annotations
from typing import Optional
"""Routes for Client management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client import Client
from app.models.enums import BusinessType, ClientStatus, UserRole
from app.dependencies import RequireRole

# Create router for operations that require agency_admin (mutations)
router = APIRouter(
    prefix="/clients",
    tags=["clients"],
)

class ClientCreate(BaseModel):
    name: str
    domain: str
    logo_url: Optional[str] = None
    business_type: BusinessType
    locale: str
    package_keywords: int
    status: ClientStatus = ClientStatus.active

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    business_type: Optional[BusinessType] = None
    locale: Optional[str] = None
    package_keywords: Optional[int] = None
    status: Optional[ClientStatus] = None

class ClientResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    domain: str
    logo_url: Optional[str]
    business_type: BusinessType
    locale: str
    package_keywords: int
    status: ClientStatus
    onboarded_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ClientResponse], dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    """List all clients."""
    return db.query(Client).all()


@router.get("/{client_id}", response_model=ClientResponse, dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))])
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    """Get a single client by ID."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=ClientResponse, status_code=201, dependencies=[Depends(RequireRole([UserRole.agency_admin]))])
def create_client(data: ClientCreate, db: Session = Depends(get_db)) -> Client:
    """Create a new client."""
    from app.models.account import Account
    
    # Normally we would derive account_id from the authenticated user.
    # Since we are single-tenant, we fetch the first account.
    account = db.query(Account).first()
    if not account:
        raise HTTPException(status_code=500, detail="System account not configured")
        
    client = Client(
        account_id=account.id,
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


@router.put("/{client_id}", response_model=ClientResponse, dependencies=[Depends(RequireRole([UserRole.agency_admin]))])
def update_client(client_id: uuid.UUID, data: ClientUpdate, db: Session = Depends(get_db)) -> Client:
    """Update an existing client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    if data.name is not None:
        client.name = data.name
    if data.domain is not None:
        client.domain = data.domain
    if data.logo_url is not None:
        client.logo_url = data.logo_url
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
