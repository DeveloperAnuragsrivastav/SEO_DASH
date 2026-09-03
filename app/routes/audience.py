from __future__ import annotations
import uuid
import datetime
from calendar import monthrange
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.metric import Metric
from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/audience",
    tags=["audience"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

@router.get("/history")
def get_audience_history(
    client_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    db: Session = Depends(get_db)
):
    query = select(Metric).where(
        Metric.client_id == client_id,
        Metric.provider == "ga4"
    )
    if start_date: query = query.where(Metric.captured_on >= start_date)
    if end_date: query = query.where(Metric.captured_on <= end_date)
    
    metrics = db.execute(query).scalars().all()
    
    from collections import defaultdict
    grouped = defaultdict(dict)
    
    for m in metrics:
        key = (m.captured_on.isoformat(), m.dimension_key, m.dimension_value)
        grouped[key][m.metric_key] = float(m.value)
        
    results = []
    for (cap_on, dim_key, dim_val), data in grouped.items():
        results.append({
            "captured_on": cap_on,
            "dimension_key": dim_key,
            "dimension_value": dim_val,
            "sessions": data.get("sessions", 0.0),
            "users": data.get("users", 0.0),
            "engaged_sessions": data.get("engaged_sessions", 0.0),
            "conversions": data.get("conversions", 0.0),
            "revenue": data.get("revenue", 0.0)
        })
        
    results.sort(key=lambda x: x["captured_on"], reverse=True)
    
    total = len(results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = results[start_idx:end_idx]
    
    return {"items": paginated, "total": total, "page": page, "page_size": page_size}

@router.get("/{month_str}")
def get_audience_metrics(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch GA4 metrics broken down by channel, device, and country."""
    try:
        target_month = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")

    start_date, end_date = get_month_boundaries(target_month.year, target_month.month)

    metrics = db.execute(
        select(Metric).where(
            Metric.client_id == client_id,
            Metric.provider == "ga4",
            Metric.dimension_key.in_(["channel", "device", "country"]),
            Metric.captured_on >= start_date,
            Metric.captured_on <= end_date
        )
    ).scalars().all()

    # Aggregate by dimension_key -> dimension_value
    from collections import defaultdict
    
    # We want format: { "channel": [ { "dimension": "Organic Search", "sessions": 100, ... } ] }
    agg = defaultdict(lambda: defaultdict(lambda: {
        "sessions": 0.0, 
        "users": 0.0, 
        "engaged_sessions": 0.0, 
        "conversions": 0.0, 
        "revenue": 0.0,
        "source": "api"
    }))

    for m in metrics:
        dim_key = m.dimension_key
        dim_val = m.dimension_value
        if not dim_key or not dim_val:
            continue
            
        if m.metric_key in agg[dim_key][dim_val]:
            agg[dim_key][dim_val][m.metric_key] += float(m.value)
            
        if m.metric_key == "sessions":
            agg[dim_key][dim_val]["source"] = m.source.value if m.source else "api"

    results = {
        "channel": [],
        "device": [],
        "country": []
    }
    
    for dim_key in ["channel", "device", "country"]:
        for dim_val, data in agg[dim_key].items():
            results[dim_key].append({
                "dimension": dim_val,
                "sessions": data["sessions"],
                "users": data["users"],
                "engaged_sessions": data["engaged_sessions"],
                "conversions": data["conversions"],
                "revenue": data["revenue"],
                "source": data["source"]
            })
            
        # Sort each list by sessions descending
        results[dim_key].sort(key=lambda x: x["sessions"], reverse=True)

    return {"data": results}


