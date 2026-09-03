from __future__ import annotations
import uuid
import datetime
import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.client import Client
from app.models.screenshot import Screenshot

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/screenshots",
    tags=["screenshots"]
)

# Standard auth dependencies
SECURED_DEPS = [Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]

@router.get("", dependencies=SECURED_DEPS)
def list_screenshots(client_id: uuid.UUID, page: int = 1, page_size: int = 25, db: Session = Depends(get_db)):
    """List all screenshots for a client."""
    from sqlalchemy import func
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    base_query = select(Screenshot).where(Screenshot.client_id == client_id)
    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0
    
    screenshots = db.execute(
        base_query.order_by(Screenshot.month.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    
    items = [
        {
            "id": s.id,
            "client_id": s.client_id,
            "month": s.month,
            "keyword_id": s.keyword_id,
            "file_url": s.file_url,
            "caption": s.caption
        }
        for s in screenshots
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.post("", status_code=status.HTTP_201_CREATED, dependencies=SECURED_DEPS)
def upload_screenshot(
    client_id: uuid.UUID,
    month: str = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a new screenshot (saved directly to DB)."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    try:
        month_date = datetime.datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    file_bytes = file.file.read()
    screenshot_id = uuid.uuid4()
    
    screenshot = Screenshot(
        id=screenshot_id,
        client_id=client_id,
        month=month_date,
        file_url=f"/clients/{client_id}/screenshots/{screenshot_id}/image",
        caption=caption.strip() if caption else None,
        file_data=file_bytes,
        mime_type=file.content_type or "image/png"
    )
    db.add(screenshot)
    db.commit()
    db.refresh(screenshot)
    
    return {
        "id": screenshot.id,
        "client_id": screenshot.client_id,
        "month": screenshot.month,
        "keyword_id": screenshot.keyword_id,
        "file_url": screenshot.file_url,
        "caption": screenshot.caption
    }


@router.post("/bulk", status_code=status.HTTP_201_CREATED, dependencies=SECURED_DEPS)
def upload_screenshots_bulk(
    client_id: uuid.UUID,
    month: str = Form(...),
    captions: List[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Upload multiple screenshots (saved directly to DB)."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    try:
        month_date = datetime.datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    uploaded = []
    
    for i, file in enumerate(files):
        file_bytes = file.file.read()
        screenshot_id = uuid.uuid4()
        
        c = captions[i].strip() if captions and i < len(captions) and captions[i] else None
        screenshot = Screenshot(
            id=screenshot_id,
            client_id=client_id,
            month=month_date,
            file_url=f"/clients/{client_id}/screenshots/{screenshot_id}/image",
            caption=c,
            file_data=file_bytes,
            mime_type=file.content_type or "image/png"
        )
        db.add(screenshot)
        uploaded.append(screenshot)
        
    db.commit()
    for s in uploaded:
        db.refresh(s)
        
    return [
        {
            "id": s.id,
            "client_id": s.client_id,
            "month": s.month,
            "keyword_id": s.keyword_id,
            "file_url": s.file_url,
            "caption": s.caption
        }
        for s in uploaded
    ]

# The actual image serving endpoint (does NOT require auth so <img src> works easily, 
# or could rely on auth if the client passes tokens, but typical img tags don't pass headers without extra work. 
# We'll leave it open under the specific client route for ease of embedding).
@router.get("/{screenshot_id}/image")
def get_screenshot_image(client_id: uuid.UUID, screenshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Serve the raw screenshot binary data."""
    screenshot = db.execute(
        select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.id == screenshot_id)
    ).scalar_one_or_none()
    
    if not screenshot or not screenshot.file_data:
        raise HTTPException(status_code=404, detail="Image not found")
        
    return Response(content=screenshot.file_data, media_type=screenshot.mime_type or "image/png")

