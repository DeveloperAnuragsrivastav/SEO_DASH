from __future__ import annotations
import uuid
import datetime
from calendar import monthrange
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.link import Link
from app.models.enums import LinkStatus, UserRole
from app.dependencies import RequireRole

router = APIRouter(
    prefix="/clients/{client_id}/links",
    tags=["links"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

class LinkCreate(BaseModel):
    domain: str
    url: str
    activity_type: str
    status: LinkStatus = LinkStatus.active
    dr: Optional[int] = None
    created_on: datetime.date

class LinkResponse(BaseModel):
    id: uuid.UUID
    domain: str
    url: str
    activity_type: str
    status: LinkStatus
    dr: Optional[int]
    last_checked: Optional[datetime.datetime]
    created_on: datetime.date

class LinksMonthResponse(BaseModel):
    kpis: dict
    links: List[LinkResponse]

@router.get("/{month_str}", response_model=LinksMonthResponse)
def get_links(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch links for the client/period with KPI summaries."""
    try:
        target_month = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")

    start_date, end_date = get_month_boundaries(target_month.year, target_month.month)

    links_db = db.execute(
        select(Link).where(
            Link.client_id == client_id,
            Link.created_on >= start_date,
            Link.created_on <= end_date
        ).order_by(Link.created_on.desc())
    ).scalars().all()

    # Calculate KPIs
    unique_domains = len(set(l.domain for l in links_db))
    activity_breakdown = {}
    for l in links_db:
        activity_breakdown[l.activity_type] = activity_breakdown.get(l.activity_type, 0) + 1

    kpis = {
        "total_links": len(links_db),
        "unique_domains": unique_domains,
        "activity_breakdown": activity_breakdown
    }

    return {
        "kpis": kpis,
        "links": links_db
    }

@router.post("", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(client_id: uuid.UUID, payload: LinkCreate, db: Session = Depends(get_db)):
    """Create a manual link entry."""
    link = Link(
        client_id=client_id,
        created_on=payload.created_on,
        activity_type=payload.activity_type,
        domain=payload.domain,
        url=payload.url,
        status=payload.status,
        dr=payload.dr,
        last_checked=None
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
