from __future__ import annotations
import os
import uuid
import shutil
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from app.models.report_month import ReportMonth
from app.models.enums import UserRole, ReportStatus
from app.dependencies import RequireRole

router = APIRouter(
    prefix="/clients/{client_id}/work",
    tags=["work"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

# Directory for screenshots
SCREENSHOTS_DIR = os.path.join(os.getcwd(), "app", "static", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

class ActivityCreate(BaseModel):
    month: datetime.date
    activity_type: str
    count: int
    notes: Optional[str] = None

class ActivityResponse(BaseModel):
    id: uuid.UUID
    month: datetime.date
    activity_type: str
    count: int
    notes: Optional[str]

class ScreenshotResponse(BaseModel):
    id: uuid.UUID
    month: datetime.date
    keyword_id: Optional[uuid.UUID]
    file_url: str
    caption: Optional[str]

class WorkMonthResponse(BaseModel):
    activities: List[ActivityResponse]
    screenshots: List[ScreenshotResponse]
    next_month_plan: Optional[dict]

class PlanUpdate(BaseModel):
    next_month_plan: Optional[dict]

@router.get("/{month_str}", response_model=WorkMonthResponse)
def get_work_done(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch activities, screenshots, and the next_month_plan for the period."""
    try:
        target_month = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")

    # Activities
    activities = db.execute(
        select(Activity).where(
            Activity.client_id == client_id,
            Activity.month == target_month
        ).order_by(Activity.activity_type)
    ).scalars().all()

    # Screenshots
    screenshots = db.execute(
        select(Screenshot).where(
            Screenshot.client_id == client_id,
            Screenshot.month == target_month
        )
    ).scalars().all()

    # Next Month Plan from ReportMonth
    report = db.execute(
        select(ReportMonth).where(
            ReportMonth.client_id == client_id,
            ReportMonth.month == target_month
        )
    ).scalar_one_or_none()

    next_month_plan = report.next_month_plan if report else None

    return {
        "activities": activities,
        "screenshots": screenshots,
        "next_month_plan": next_month_plan
    }

@router.post("/activities", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity(client_id: uuid.UUID, payload: ActivityCreate, db: Session = Depends(get_db)):
    """Create a manual activity entry."""
    activity = Activity(
        client_id=client_id,
        month=payload.month,
        activity_type=payload.activity_type,
        count=payload.count,
        notes=payload.notes
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity

@router.post("/screenshots", response_model=ScreenshotResponse, status_code=status.HTTP_201_CREATED)
def upload_screenshot(
    client_id: uuid.UUID,
    month: str = Form(...),
    caption: Optional[str] = Form(None),
    keyword_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a screenshot file."""
    try:
        target_month = datetime.datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        try:
            target_month = datetime.datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM or YYYY-MM-DD")

    file_extension = os.path.splitext(file.filename)[1] if file.filename else ".png"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(SCREENSHOTS_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Relative URL to serve via StaticFiles
    file_url = f"/static/screenshots/{unique_filename}"

    parsed_kw_id = None
    if keyword_id and keyword_id.strip():
        try:
            parsed_kw_id = uuid.UUID(keyword_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid keyword_id format")

    screenshot = Screenshot(
        client_id=client_id,
        month=target_month,
        keyword_id=parsed_kw_id,
        file_url=file_url,
        caption=caption
    )
    db.add(screenshot)
    db.commit()
    db.refresh(screenshot)
    return screenshot

@router.delete("/screenshots/{screenshot_id}")
def delete_screenshot(
    client_id: uuid.UUID,
    screenshot_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Delete a screenshot record and its associated file."""
    screenshot = db.execute(
        select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.id == screenshot_id)
    ).scalar_one_or_none()
    
    if not screenshot:
        raise HTTPException(status_code=404, detail="Screenshot not found")
        
    if screenshot.file_url:
        filename = screenshot.file_url.split("/")[-1]
        file_path = os.path.join(SCREENSHOTS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    db.delete(screenshot)
    db.commit()
    return {"status": "success"}


@router.put("/{month_str}/plan")
def update_plan(client_id: uuid.UUID, month_str: str, payload: PlanUpdate, db: Session = Depends(get_db)):
    """Edit the next_month_plan of a draft/review report."""
    target_month = datetime.date.fromisoformat(f"{month_str}-01")
    
    report = db.execute(
        select(ReportMonth).where(ReportMonth.client_id == client_id, ReportMonth.month == target_month)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a published report.")
        
    report.next_month_plan = payload.next_month_plan
    db.commit()
    
    return {"status": "success", "next_month_plan": report.next_month_plan}
