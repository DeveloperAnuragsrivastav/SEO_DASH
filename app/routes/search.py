from __future__ import annotations
import uuid
import datetime
from calendar import monthrange
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.metric import Metric
from app.models.enums import MetricSource
from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/search",
    tags=["search"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

@router.get("/history")
def get_search_history(
    client_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    db: Session = Depends(get_db)
):
    query = select(Metric).where(
        Metric.client_id == client_id,
        Metric.provider == "gsc",
        Metric.dimension_key.in_(["page", "query", "device", "country"])
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
            "clicks": data.get("clicks", 0.0),
            "impressions": data.get("impressions", 0.0),
            "ctr": data.get("ctr", 0.0),
            "position": data.get("position", 0.0)
        })
        
    results.sort(key=lambda x: x["captured_on"], reverse=True)
    
    total = len(results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = results[start_idx:end_idx]
    
    return {"items": paginated, "total": total, "page": page, "page_size": page_size}

@router.get("/{month_str}")
def get_search_performance(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch GSC metrics with dimension_key='page' for the target month and the previous month."""
    try:
        target_month = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")

    start_date, end_date = get_month_boundaries(target_month.year, target_month.month)
    
    prev_month = target_month - relativedelta(months=1)
    prev_start, prev_end = get_month_boundaries(prev_month.year, prev_month.month)

    # Fetch current month page metrics
    curr_metrics = db.execute(
        select(Metric).where(
            Metric.client_id == client_id,
            Metric.provider == "gsc",
            Metric.dimension_key == "page",
            Metric.captured_on >= start_date,
            Metric.captured_on <= end_date
        )
    ).scalars().all()

    # Fetch previous month page metrics
    prev_metrics = db.execute(
        select(Metric).where(
            Metric.client_id == client_id,
            Metric.provider == "gsc",
            Metric.dimension_key == "page",
            Metric.captured_on >= prev_start,
            Metric.captured_on <= prev_end
        )
    ).scalars().all()

    # Aggregate by dimension_value (the page URL)
    from collections import defaultdict
    curr_data = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "ctr_sum": 0.0, "pos_sum": 0.0, "count": 0, "source": None})
    prev_data = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0})

    for m in curr_metrics:
        page = m.dimension_value
        if not page:
            continue
        curr_data[page]["clicks"] += float(m.value) if m.metric_key == "clicks" else 0
        curr_data[page]["impressions"] += float(m.value) if m.metric_key == "impressions" else 0
        
        if m.metric_key == "ctr":
            curr_data[page]["ctr_sum"] += float(m.value)
            curr_data[page]["count"] += 1
        if m.metric_key == "position":
            curr_data[page]["pos_sum"] += float(m.value)
        
        if m.metric_key == "clicks": # Just grab source from clicks
            curr_data[page]["source"] = m.source.value if m.source else "api"

    for m in prev_metrics:
        page = m.dimension_value
        if not page:
            continue
        prev_data[page]["clicks"] += float(m.value) if m.metric_key == "clicks" else 0
        prev_data[page]["impressions"] += float(m.value) if m.metric_key == "impressions" else 0

    results = []
    
    for page, data in curr_data.items():
        curr_clicks = data["clicks"]
        prev_clicks = prev_data[page]["clicks"]
        
        categories = []
        
        # New
        if prev_clicks == 0 and curr_clicks > 0:
            categories.append("New")
        elif prev_clicks > 0:
            change_pct = ((curr_clicks - prev_clicks) / prev_clicks) * 100
            if change_pct > 15:
                categories.append("Trending Up")
            elif change_pct < -15:
                categories.append("Trending Down")
                
        # Top classification happens after we sort
        
        ctr = data["ctr_sum"] / data["count"] if data["count"] > 0 else 0
        avg_pos = data["pos_sum"] / data["count"] if data["count"] > 0 else 0

        results.append({
            "url": page,
            "clicks": curr_clicks,
            "impressions": data["impressions"],
            "ctr": ctr,
            "position": avg_pos,
            "categories": categories,
            "source": data["source"] or "api"
        })

    # Sort by clicks descending to assign "Top"
    results.sort(key=lambda x: x["clicks"], reverse=True)
    
    # Top 20 pages get the "Top" category
    for i, res in enumerate(results):
        if i < 20:
            res["categories"].append("Top")

    return {"data": results}
