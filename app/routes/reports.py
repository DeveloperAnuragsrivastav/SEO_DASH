from __future__ import annotations
import datetime
import logging
import uuid
from typing import Any

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models.ai_mention import AiMention
from app.models.activity import Activity
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, ReportStatus, MetricSource
from app.models.link import Link
from app.models.keyword import Keyword
from app.models.metric import Metric
from app.models.ranking import Ranking
from app.models.report_month import ReportMonth
from app.models.screenshot import Screenshot
from app.services.ga4_service import pull_ga4_data
from app.services.gbp_service import pull_gbp_data
from app.services.groq_service import generate_report_narrative
from app.services.gsc_service import pull_gsc_data
from calendar import monthrange

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

logger = logging.getLogger(__name__)

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/reports",
    tags=["reports"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)


class ReportGenerateRequest(BaseModel):
    month: datetime.date


class ReportUpdateNarrativeRequest(BaseModel):
    narrative: str


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_report(client_id: uuid.UUID, payload: ReportGenerateRequest, db: Session = Depends(get_db)):
    """Generate the monthly SEO report (Phase 11)."""
    
    # 1. Concurrency Control (Advisory Lock)
    lock_id = hash(f"{client_id}-{payload.month.strftime('%Y-%m')}") & 0x7FFFFFFFFFFFFFFF
    
    with engine.connect() as lock_conn:
        acquired = lock_conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report generation is already in progress for this client and month."
            )
            
        try:
            # Verify client exists
            client = db.get(Client, client_id)
            if not client:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")
                
            # Check unique constraint proactively
            existing = db.execute(
                select(ReportMonth).where(ReportMonth.client_id == client_id, ReportMonth.month == payload.month)
            ).scalar_one_or_none()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Report for this month already exists."
                )

            # Boundaries
            start_date, end_date = get_month_boundaries(payload.month.year, payload.month.month)
            
            prev_month = payload.month - relativedelta(months=1)
            prev_start, prev_end = get_month_boundaries(prev_month.year, prev_month.month)

            # 2. Data Resolution (Live Pulls)
            connections = db.execute(
                select(Connection).where(Connection.client_id == client_id)
            ).scalars().all()
            
            for conn in connections:
                if conn.status == ConnectionStatus.connected:
                    try:
                        if conn.provider == ProviderType.gsc:
                            pull_gsc_data(db, conn.id, start_date, end_date)
                        elif conn.provider == ProviderType.ga4:
                            pull_ga4_data(db, conn.id, start_date, end_date)
                        elif conn.provider == ProviderType.gbp:
                            pull_gbp_data(db, conn.id, start_date, end_date)
                    except Exception as e:
                        logger.error(f"Live pull failed for {conn.provider.value}: {e}")
                        # Fallback to manual metrics natively handled by DB query later

            # Build Snapshot
            snapshot: dict[str, Any] = {
                "gsc": _resolve_metrics(db, client_id, start_date, end_date, "gsc"),
                "ga4": _resolve_metrics(db, client_id, start_date, end_date, "ga4"),
                "gbp": _resolve_metrics(db, client_id, start_date, end_date, "gbp"),
                "rankings": _resolve_rankings(db, client_id, start_date, end_date, prev_start, prev_end),
                "ai_visibility": _resolve_ai_visibility(db, client_id, start_date, end_date),
                "links": _resolve_links(db, client_id, start_date, end_date),
                "activities": _resolve_activities(db, client_id, start_date, end_date),
                "screenshots": _resolve_screenshots(db, client_id, start_date, end_date),
            }

            # KPI Deltas
            prev_snapshot = {
                "gsc": _resolve_metrics(db, client_id, prev_start, prev_end, "gsc"),
                "ga4": _resolve_metrics(db, client_id, prev_start, prev_end, "ga4"),
                "gbp": _resolve_metrics(db, client_id, prev_start, prev_end, "gbp"),
            }
            snapshot["kpi_deltas"] = _compute_kpi_deltas(snapshot, prev_snapshot)

            # 3. Narrative Auto-Draft
            try:
                narrative = generate_report_narrative(client.name, payload.month.strftime("%B %Y"), snapshot)
            except Exception as e:
                logger.error(f"Groq narrative generation failed: {e}")
                narrative = "Narrative auto-generation failed. Please draft manually."

            # 4. Write Report
            report = ReportMonth(
                client_id=client_id,
                month=payload.month,
                status=ReportStatus.draft,
                snapshot=snapshot,
                narrative=narrative,
                generated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(report)
            db.commit()
            
            return {
                "id": report.id,
                "client_id": report.client_id,
                "month": report.month,
                "status": report.status,
                "narrative": report.narrative
            }
            
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})


@router.put("/{month_str}")
def update_report_narrative(client_id: uuid.UUID, month_str: str, payload: ReportUpdateNarrativeRequest, db: Session = Depends(get_db)):
    """Edit the narrative of a draft/review report."""
    target_month = datetime.date.fromisoformat(f"{month_str}-01")
    
    report = db.execute(
        select(ReportMonth).where(ReportMonth.client_id == client_id, ReportMonth.month == target_month)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a published report.")
        
    report.narrative = payload.narrative
    db.commit()
    
    return {"status": "success", "narrative": report.narrative}


from app.models.user import User
from app.dependencies import get_current_user

@router.post("/{month_str}/publish", dependencies=[Depends(RequireRole([UserRole.agency_admin]))])
def publish_report(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Publish the report."""
    target_month = datetime.date.fromisoformat(f"{month_str}-01")
    
    report = db.execute(
        select(ReportMonth).where(ReportMonth.client_id == client_id, ReportMonth.month == target_month)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Report is already published.")
        
    report.status = ReportStatus.published
    report.published_at = datetime.datetime.now(datetime.timezone.utc)
    report.published_by = current_user.id
    
    db.commit()
    
    return {"status": "success", "published_at": report.published_at}


@router.get("/{month_str}")
def get_report(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch a specific report by client and month."""
    target_month = datetime.date.fromisoformat(f"{month_str}-01")
    
    report = db.execute(
        select(ReportMonth).where(ReportMonth.client_id == client_id, ReportMonth.month == target_month)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    return {
        "id": report.id,
        "client_id": report.client_id,
        "month": report.month,
        "status": report.status,
        "snapshot": report.snapshot,
        "narrative": report.narrative,
        "generated_at": report.generated_at,
        "published_at": report.published_at,
        "published_by": report.published_by
    }


# --- Helpers ---

def _resolve_metrics(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date, provider: str) -> dict:
    metrics = db.execute(
        select(Metric).where(
            Metric.client_id == client_id,
            Metric.provider == provider,
            Metric.captured_on >= start_date,
            Metric.captured_on <= end_date
        )
    ).scalars().all()
    
    from collections import defaultdict
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))
    
    for m in metrics:
        # Ignore dimension-level rows for the top-level summary to avoid double counting
        if m.dimension_key:
            continue
            
        sums[m.metric_key][m.source] += float(m.value)
        counts[m.metric_key][m.source] += 1
        
    resolved = {}
    for key in sums:
        # Priority: API over Manual
        src = MetricSource.api if MetricSource.api in sums[key] else MetricSource.manual
        
        # Average for rates/positions, otherwise Sum
        if key in ["ctr", "position", "averageSessionDuration"]:
            resolved[key] = round(sums[key][src] / counts[key][src], 2)
        else:
            resolved[key] = round(sums[key][src], 2)
                
    return resolved


def _resolve_rankings(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date, prev_start: datetime.date, prev_end: datetime.date) -> dict:
    current_rankings = db.execute(
        select(Ranking).join(Keyword).where(
            Keyword.client_id == client_id,
            Ranking.captured_on >= start_date,
            Ranking.captured_on <= end_date
        )
    ).scalars().all()
    
    prev_rankings = db.execute(
        select(Ranking).join(Keyword).where(
            Keyword.client_id == client_id,
            Ranking.captured_on >= prev_start,
            Ranking.captured_on <= prev_end
        )
    ).scalars().all()
    
    prev_map = {r.keyword_id: r.position for r in prev_rankings}
    
    summary = {
        "improved": 0,
        "declined": 0,
        "top_10": 0,
        "11_20": 0,
        "21_50": 0,
        "51_plus": 0
    }
    
    keywords_list = []
    
    for r in current_rankings:
        pos = r.position
        prev_pos = prev_map.get(r.keyword_id)
        
        if prev_pos:
            if pos < prev_pos:
                summary["improved"] += 1
            elif pos > prev_pos:
                summary["declined"] += 1
                
        if pos <= 10:
            summary["top_10"] += 1
        elif pos <= 20:
            summary["11_20"] += 1
        elif pos <= 50:
            summary["21_50"] += 1
        else:
            summary["51_plus"] += 1
            
        keywords_list.append({
            "keyword_id": str(r.keyword_id),
            "position": pos,
            "previous_position": prev_pos
        })
        
    return {
        "summary": summary,
        "keywords": keywords_list
    }


def _resolve_ai_visibility(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:

    mentions = db.execute(
        select(AiMention).where(
            AiMention.client_id == client_id,
            AiMention.captured_on >= start_date,
            AiMention.captured_on <= end_date
        )
    ).scalars().all()
    
    return [
        {
            "prompt_id": str(m.prompt_id) if m.prompt_id else None,
            "platform": m.platform.value,
            "mentioned": m.mentioned,
            "cited_pages": m.cited_pages
        }
        for m in mentions
    ]


def _resolve_links(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    links = db.execute(
        select(Link).where(Link.client_id == client_id, Link.created_on >= start_date, Link.created_on <= end_date, Link.status == "active")
    ).scalars().all()
    return [{"id": str(l.id), "url": l.url, "domain": l.domain, "activity_type": l.activity_type} for l in links]


def _resolve_activities(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    activities = db.execute(
        select(Activity).where(Activity.client_id == client_id, Activity.month == start_date)
    ).scalars().all()
    return [{"month": str(a.month), "activity_type": a.activity_type, "count": a.count, "notes": a.notes} for a in activities]


def _resolve_screenshots(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    screenshots = db.execute(
        select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.month == start_date)
    ).scalars().all()
    return [{"month": str(s.month), "file_url": s.file_url, "caption": s.caption} for s in screenshots]


def _compute_kpi_deltas(snapshot: dict, prev_snapshot: dict) -> dict:
    deltas = {}
    for provider in ["gsc", "ga4", "gbp"]:
        deltas[provider] = {}
        for k, v in snapshot[provider].items():
            prev_v = prev_snapshot[provider].get(k, 0)
            deltas[provider][k] = v - prev_v
    return deltas
