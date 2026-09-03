from __future__ import annotations
import uuid
import datetime
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.client import Client
from app.models.screenshot import Screenshot

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/screenshots",
    tags=["screenshots"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

SCREENSHOTS_DIR = os.path.join(os.getcwd(), "app", "static", "screenshots")

@router.get("")
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

@router.post("", status_code=status.HTTP_201_CREATED)
def upload_screenshot(
    client_id: uuid.UUID,
    month: str = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a new screenshot."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    try:
        month_date = datetime.datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(SCREENSHOTS_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_url = f"/static/screenshots/{unique_filename}"
    
    screenshot = Screenshot(
        client_id=client_id,
        month=month_date,
        file_url=file_url,
        caption=caption.strip() if caption else None
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

from typing import List

@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def upload_screenshots_bulk(
    client_id: uuid.UUID,
    month: str = Form(...),
    captions: List[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Upload multiple screenshots."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    try:
        month_date = datetime.datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    uploaded = []
    
    for i, file in enumerate(files):
        file_extension = file.filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(SCREENSHOTS_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_url = f"/static/screenshots/{unique_filename}"
        
        c = captions[i].strip() if captions and i < len(captions) and captions[i] else None
        screenshot = Screenshot(
            client_id=client_id,
            month=month_date,
            file_url=file_url,
            caption=c
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

