"""The client's month-on-month sheets (sidebar: Search Console, Analytics…).

Read by everyone who can see the client. A month appears once its report is
published; anyone who can see the client may correct a figure after that.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import RequireRole
from app.models.enums import ReportStatus, UserRole
from app.models.report_image import ReportImage
from app.models.report_snapshot import ReportSnapshot
from app.models.user import User
from app.services import sheets

ANYONE = RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user])

router = APIRouter(prefix="/clients/{client_id}/sheets", tags=["sheets"])


def _sheet(sheet: str) -> str:
    if sheet not in sheets.SHEET_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown sheet.")
    return sheet


def _month(raw: str) -> datetime.date:
    try:
        return sheets.month_of(datetime.date.fromisoformat(raw if len(raw) > 7 else f"{raw}-01"))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Use a month like 2026-09.")


from app.services.report_period import period_name  # noqa: E402


@router.get("/screenshots/months")
def screenshot_months(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(ANYONE)):
    """Every published report's screenshots, newest month first."""
    reports = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id,
                                     ReportSnapshot.status == ReportStatus.published)
        .order_by(ReportSnapshot.end_date.desc())
    ).scalars().all()
    images: dict[uuid.UUID, list] = {}
    if reports:
        for img in db.execute(
            select(ReportImage).where(ReportImage.report_id.in_([r.id for r in reports]))
            .order_by(ReportImage.section, ReportImage.slot)
        ).scalars():
            images.setdefault(img.report_id, []).append(
                {"section": img.section, "slot": img.slot, "caption": img.caption or ""})
    return [
        {"month": sheets.report_month(r).isoformat(),
         "label": period_name(r.start_date, r.end_date) if r.start_date else f"{sheets.report_month(r):%B %Y}",
         "report": str(r.id), "images": images.get(r.id, [])}
        for r in reports
    ]


@router.get("/{sheet}")
def get_sheet(client_id: uuid.UUID, sheet: str, db: Session = Depends(get_db), user: User = Depends(ANYONE)):
    view = sheets.sheet_view(db, client_id, _sheet(sheet))
    return {**view, "editable": True}


@router.get("/{sheet}/details/{month}")
def get_month_details(client_id: uuid.UUID, sheet: str, month: str, db: Session = Depends(get_db),
                      user: User = Depends(ANYONE)):
    """The entries behind a month's counts (each link, each task)."""
    return sheets.month_details(db, client_id, _sheet(sheet), _month(month))


class CellEdit(BaseModel):
    row: str
    month: str
    value: Optional[float] = None
    text: Optional[str] = None


@router.put("/{sheet}/cell")
def edit_sheet_cell(client_id: uuid.UUID, sheet: str, data: CellEdit, db: Session = Depends(get_db),
                    user: User = Depends(ANYONE)):
    if data.value is not None and data.value < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Figures cannot be negative.")
    try:
        cell = sheets.edit_cell(db, client_id, _sheet(sheet), data.row, _month(data.month),
                                data.value, data.text, user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    db.commit()
    return cell


@router.delete("/{sheet}/rows/{row_key:path}")
def stop_tracking(client_id: uuid.UUID, sheet: str, row_key: str, db: Session = Depends(get_db),
                  user: User = Depends(ANYONE)):
    """Stop tracking a keyword or prompt: later reports leave it out. Its
    published months stay on the sheet."""
    from app.models.ai_prompt import AiPrompt
    from app.models.keyword import Keyword
    model, prefix = {"keywords": (Keyword, "kw:"), "ai": (AiPrompt, "prompt:")}.get(_sheet(sheet), (None, None))
    if model is None or not row_key.startswith(prefix):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Only keywords and prompts are tracked.")
    try:
        row = db.get(model, uuid.UUID(row_key[len(prefix):]))
    except ValueError:
        row = None
    if row is None or row.client_id != client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    row.is_active = False
    db.commit()
    return {"row": row_key, "tracked": False}
