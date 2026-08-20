from __future__ import annotations
from typing import Optional
"""Routes for Manual Metrics entry."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import MetricSource
from app.models.metric import Metric

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}",
    tags=["manual_metrics"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)


class ManualGSCRecord(BaseModel):
    captured_on: date
    clicks: int = Field(ge=0)
    impressions: int = Field(ge=0)
    ctr: float = Field(ge=0.0, le=1.0)
    position: float = Field(gt=0.0)
    dimension_key: Optional[str] = None
    dimension_value: Optional[str] = None


class ManualGSCInput(BaseModel):
    records: list[ManualGSCRecord]


@router.post("/manual-gsc", status_code=201)
def create_manual_gsc_metrics(
    client_id: uuid.UUID,
    data: ManualGSCInput,
    db: Session = Depends(get_db),
) -> dict:
    """Manually enter GSC metrics for a client."""

    metrics_to_insert = []

    for record in data.records:
        for metric_key, val in [
            ("clicks", float(record.clicks)),
            ("impressions", float(record.impressions)),
            ("ctr", record.ctr),
            ("position", record.position),
        ]:
            metrics_to_insert.append(
                Metric(
                    client_id=client_id,
                    provider="gsc",
                    metric_key=metric_key,
                    dimension_key=record.dimension_key,
                    dimension_value=record.dimension_value,
                    captured_on=record.captured_on,
                    value=val,
                    source=MetricSource.manual,
                )
            )

    if metrics_to_insert:
        db.add_all(metrics_to_insert)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return {"status": "success", "rows_inserted": len(metrics_to_insert)}


class ManualGA4Record(BaseModel):
    captured_on: date
    sessions: int = Field(ge=0)
    users: int = Field(ge=0)
    engaged_sessions: int = Field(ge=0)
    conversions: int = Field(ge=0)
    revenue: float = Field(ge=0.0)
    dimension_key: Optional[str] = None
    dimension_value: Optional[str] = None


class ManualGA4Input(BaseModel):
    records: list[ManualGA4Record]


@router.post("/manual-ga4", status_code=201)
def create_manual_ga4_metrics(
    client_id: uuid.UUID,
    data: ManualGA4Input,
    db: Session = Depends(get_db),
) -> dict:
    """Manually enter GA4 metrics for a client."""

    metrics_to_insert = []

    for record in data.records:
        for metric_key, val in [
            ("sessions", float(record.sessions)),
            ("users", float(record.users)),
            ("engaged_sessions", float(record.engaged_sessions)),
            ("conversions", float(record.conversions)),
            ("revenue", record.revenue),
        ]:
            metrics_to_insert.append(
                Metric(
                    client_id=client_id,
                    provider="ga4",
                    metric_key=metric_key,
                    dimension_key=record.dimension_key,
                    dimension_value=record.dimension_value,
                    captured_on=record.captured_on,
                    value=val,
                    source=MetricSource.manual,
                )
            )

    if metrics_to_insert:
        db.add_all(metrics_to_insert)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return {"status": "success", "rows_inserted": len(metrics_to_insert)}


class ManualGBPRecord(BaseModel):
    captured_on: date
    impressions_desktop_maps: int = Field(ge=0)
    impressions_desktop_search: int = Field(ge=0)
    impressions_mobile_maps: int = Field(ge=0)
    impressions_mobile_search: int = Field(ge=0)
    calls: int = Field(ge=0)
    direction_requests: int = Field(ge=0)
    website_clicks: int = Field(ge=0)
    bookings: int = Field(ge=0)


class ManualGBPInput(BaseModel):
    records: list[ManualGBPRecord]


@router.post("/manual-gbp", status_code=201)
def create_manual_gbp_metrics(
    client_id: uuid.UUID,
    data: ManualGBPInput,
    db: Session = Depends(get_db),
) -> dict:
    """Manually enter GBP metrics for a client."""

    metrics_to_insert = []

    for record in data.records:
        for metric_key, val in [
            ("impressions_desktop_maps", float(record.impressions_desktop_maps)),
            ("impressions_desktop_search", float(record.impressions_desktop_search)),
            ("impressions_mobile_maps", float(record.impressions_mobile_maps)),
            ("impressions_mobile_search", float(record.impressions_mobile_search)),
            ("calls", float(record.calls)),
            ("direction_requests", float(record.direction_requests)),
            ("website_clicks", float(record.website_clicks)),
            ("bookings", float(record.bookings)),
        ]:
            metrics_to_insert.append(
                Metric(
                    client_id=client_id,
                    provider="gbp",
                    metric_key=metric_key,
                    dimension_key=None,
                    dimension_value=None,
                    captured_on=record.captured_on,
                    value=val,
                    source=MetricSource.manual,
                )
            )

    if metrics_to_insert:
        db.add_all(metrics_to_insert)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return {"status": "success", "rows_inserted": len(metrics_to_insert)}
