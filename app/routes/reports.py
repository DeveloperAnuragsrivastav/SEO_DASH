from __future__ import annotations
import datetime
import logging
import uuid
from typing import Any, Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import engine, get_db
from app.models.ai_mention import AiMention
from app.models.ai_prompt import AiPrompt
from app.models.activity import Activity
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, ReportStatus, MetricSource
from app.models.link import Link
from app.models.keyword import Keyword
from app.models.metric import Metric
from app.models.ranking import Ranking
from app.models.report_snapshot import ReportSnapshot
from app.models.screenshot import Screenshot
from app.services.ga4_service import pull_ga4_data
from app.services import report_composer as composer
from app.services.openai_service import suggest_report_sections
from app.services.gbp_service import pull_gbp_data
from app.services.openai_service import generate_report_narrative
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
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)


class ReportGenerateRequest(BaseModel):
    month: datetime.date


class ReportUpdateNarrativeRequest(BaseModel):
    narrative: str


class ReportHistoryResponse(BaseModel):
    id: uuid.UUID
    start_date: datetime.date
    end_date: datetime.date
    status: ReportStatus
    generated_at: datetime.datetime | None
    published_at: datetime.datetime | None
    
    model_config = {"from_attributes": True}


@router.post("/generate")
def generate_report(client_id: uuid.UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate the monthly SEO report asynchronously."""
    
    # Verify client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")
        
    # Enforce 30-day gate
    last_snapshot = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
    ).scalars().first()
    
    end_date = datetime.date.today() - datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=29)
    
    if last_snapshot:
        days_since = (end_date - last_snapshot.end_date).days
        if days_since < 30:
            days_remaining = 30 - days_since
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Please wait {days_remaining} more days to generate the next report."
            )
    from app.models.connection import Connection
    from app.models.enums import ConnectionStatus
    from app.models.keyword import Keyword
    from app.models.ai_prompt import AiPrompt
    from app.models.ai_mention import AiMention
    from app.models.link import Link
    from app.models.activity import Activity
    from app.models.screenshot import Screenshot
    import calendar

    # Verify that the client has at least SOME manual data in the rolling window
    
    has_conn = db.execute(select(Connection).where(Connection.client_id == client_id, Connection.status == ConnectionStatus.connected)).first() is not None
    has_kw = db.execute(select(Keyword).where(Keyword.client_id == client_id)).first() is not None
    has_ap = db.execute(select(AiPrompt).where(AiPrompt.client_id == client_id)).first() is not None
    has_am = db.execute(select(AiMention).where(AiMention.client_id == client_id, AiMention.captured_on >= start_date, AiMention.captured_on <= end_date)).first() is not None
    has_lnk = db.execute(select(Link).where(Link.client_id == client_id, Link.created_on >= start_date, Link.created_on <= end_date)).first() is not None
    # Activities and Screenshots are stored per-month currently, so we check if they fall in the range
    has_act = db.execute(select(Activity).where(Activity.client_id == client_id, Activity.month >= start_date, Activity.month <= end_date)).first() is not None
    has_scr = db.execute(select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.month >= start_date, Screenshot.month <= end_date)).first() is not None

    has_manual_data = any([has_kw, has_ap, has_am, has_lnk, has_act, has_scr])

    if not has_manual_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate report: Manual data is missing. Please upload your manual data first."
        )

    # Dispatch to BackgroundTasks instead of Celery (since Railway doesn't run a Celery worker by default)
    from app.tasks.reports import generate_snapshot_report
    
    task_id = str(uuid.uuid4())
    background_tasks.add_task(generate_snapshot_report, str(client_id))
    
    return {
        "status": "processing",
        "task_id": task_id,
        "message": "Report generation has been queued."
    }


@router.put("/{snapshot_id}")
def update_report_narrative(client_id: uuid.UUID, snapshot_id: uuid.UUID, payload: ReportUpdateNarrativeRequest, db: Session = Depends(get_db)):
    """Edit the narrative of a draft/review report."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
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

@router.post("/{snapshot_id}/publish", dependencies=[Depends(RequireRole([UserRole.super_admin]))])
def publish_report(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Publish the report."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
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



class SectionSelection(BaseModel):
    sections: dict[str, bool] | None = None
    items: dict[str, bool] | None = None


class ItemEdits(BaseModel):
    edits: dict[str, Any]


class SectionSuggestRequest(BaseModel):
    instruction: str


def _load_draft(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session) -> ReportSnapshot:
    report = db.execute(
        select(ReportSnapshot).where(
            ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id
        )
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return report


@router.get("/{snapshot_id}/composer")
def get_composer(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Everything the composer needs: sections, every datum, and current state."""
    report = _load_draft(client_id, snapshot_id, db)
    snapshot = report.snapshot or {}

    # The snapshot stores prompt ids, not their text — resolve them so the
    # composer shows something a person can actually tell apart.
    prompt_labels = {
        str(pid): text_
        for pid, text_ in db.execute(
            select(AiPrompt.id, AiPrompt.prompt_text).where(AiPrompt.client_id == client_id)
        ).all()
    }

    return {
        "sections": composer.SECTIONS,
        "available": composer.section_availability(snapshot),
        "selectedSections": composer.current_sections(snapshot),
        "items": composer.enumerate_items(snapshot, prompt_labels),
        "selectedItems": composer.current_items(snapshot),
        "editable": report.status != ReportStatus.published,
    }


@router.put("/{snapshot_id}/composer")
def set_composer(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: SectionSelection,
    db: Session = Depends(get_db),
):
    """Save which sections and which individual figures the report shows."""
    report = _load_draft(client_id, snapshot_id, db)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Published reports cannot be edited.")

    snapshot = dict(report.snapshot or {})
    available = composer.section_availability(snapshot)

    if data.sections is not None:
        current = composer.current_sections(snapshot)
        snapshot["included_sections"] = {
            k: bool(data.sections.get(k, current[k])) and available[k]
            for k in composer.SECTION_KEYS
        }

    if data.items is not None:
        current_items = composer.current_items(snapshot)
        snapshot["included_items"] = {
            i: bool(data.items.get(i, current_items[i])) for i in current_items
        }

    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()

    return {
        "selectedSections": composer.current_sections(snapshot),
        "selectedItems": composer.current_items(snapshot),
    }


@router.put("/{snapshot_id}/values")
def set_composer_values(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: ItemEdits,
    db: Session = Depends(get_db),
):
    """Overwrite individual figures on a draft report.

    Period-on-period deltas for headline figures are re-derived from the
    previous period implied by the existing delta, so an edited number can never
    sit beside a percentage that contradicts it.
    """
    report = _load_draft(client_id, snapshot_id, db)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Published reports cannot be edited.")

    snapshot = dict(report.snapshot or {})
    deltas = dict(snapshot.get("kpi_deltas") or {})
    applied, rejected = [], []

    for item_id, raw in data.edits.items():
        parts = item_id.split(".")
        is_headline = len(parts) == 2 and parts[0] in composer.HEADLINE

        if is_headline:
            provider, key = parts
            try:
                new_value = float(raw)
            except (TypeError, ValueError):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{item_id} must be a number.")
            if new_value < 0:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{item_id} cannot be negative.")

            old_value = float((snapshot.get(provider) or {}).get(key) or 0)
            provider_deltas = dict(deltas.get(provider) or {})
            if key in provider_deltas:
                previous = old_value - float(provider_deltas.get(key) or 0)
                provider_deltas[key] = new_value - previous
                deltas[provider] = provider_deltas

        if composer.write_edit(snapshot, item_id, raw):
            applied.append(item_id)
        else:
            rejected.append(item_id)

    snapshot["kpi_deltas"] = deltas
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()

    return {"applied": applied, "rejected": rejected, "items": composer.enumerate_items(snapshot)}


@router.post("/{snapshot_id}/composer/suggest")
def suggest_composer(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: SectionSuggestRequest,
    db: Session = Depends(get_db),
):
    """Turn a plain-language instruction into a selection.

    Nothing is saved here — the result is handed back for the user to confirm.
    """
    report = _load_draft(client_id, snapshot_id, db)
    snapshot = report.snapshot or {}

    try:
        return suggest_report_sections(
            instruction=data.instruction,
            sections=composer.current_sections(snapshot),
            items=composer.enumerate_items(snapshot),
            item_state=composer.current_items(snapshot),
            available=composer.section_availability(snapshot),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


@router.get("/history", response_model=list[ReportHistoryResponse])
def get_report_history(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch a lightweight history of all generated report snapshots."""
    snapshots = db.execute(
        select(ReportSnapshot)
        .where(ReportSnapshot.client_id == client_id)
        .order_by(ReportSnapshot.end_date.desc())
    ).scalars().all()
    
    return snapshots


from fastapi.responses import StreamingResponse
import io

@router.get("/multi")
def get_multi_report(client_id: uuid.UUID, count: int = 1, db: Session = Depends(get_db)):
    """Fetch multiple snapshots and return them as a unified comparative structure."""
    snapshots = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc()).limit(count)
    ).scalars().all()
    
    if not snapshots:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reports not found.")
        
    snapshots.reverse()
    comparative_data = _build_comparative_report(snapshots)
    return {
        "id": "multi",
        "client_id": str(client_id),
        "status": "published",
        "generated_at": snapshots[-1].generated_at,
        "published_at": snapshots[-1].published_at,
        "end_date": snapshots[-1].end_date,
        "narrative": snapshots[-1].narrative,
        "snapshot": comparative_data
    }


@router.get("/multi/pdf")
async def download_report_pdf(request: Request, client_id: uuid.UUID, count: int = 1, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    """Generate and return a PDF of the report using Playwright/Chromium."""
    if snapshot_id:
        snapshots = db.execute(
            select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
        ).scalars().all()
    else:
        snapshots = db.execute(
            select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc()).limit(count)
        ).scalars().all()
    
    if not snapshots:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reports not found.")
    
    # Render chronologically (oldest first in the PDF)
    snapshots.reverse()
    
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")
    
    comparative_data = _build_comparative_report(snapshots)
    
    client_logo_url = client.logo_url
    client_logo_b64 = ""
    if client_logo_url and client_logo_url.strip():
        import httpx
        import base64
        fetch_url = base_url + client_logo_url if client_logo_url.startswith("/") else client_logo_url
        try:
            with httpx.Client(timeout=5.0) as c:
                resp = c.get(fetch_url)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    ctype = resp.headers.get("content-type", "image/png")
                    client_logo_b64 = f"data:{ctype};base64,{b64}"
        except Exception:
            pass

    client_data = {
        "name": client.name,
        "domain": client.domain,
        "logo_url": client.logo_url,
        "logo_b64": client_logo_b64,
        "theme_color": client.theme_color,
    }
    
    base_url = str(request.base_url).rstrip("/")
    
    # Inject base64 screenshots directly to avoid Playwright network issues
    import base64
    for img in comparative_data.get("screenshots", []):
        file_url = img.get("file_url")
        if file_url:
            parts = file_url.split("/")
            if len(parts) >= 5 and parts[-1] == "image":
                sid = parts[-2]
                s_obj = db.execute(select(Screenshot).where(Screenshot.id == sid)).scalar_one_or_none()
                if s_obj and s_obj.file_data:
                    b64 = base64.b64encode(s_obj.file_data).decode("utf-8")
                    img["base64_data"] = f"data:{s_obj.mime_type or 'image/png'};base64,{b64}"

    
    from app.services.pdf_service import generate_report_pdf as gen_pdf
    pdf_bytes = await gen_pdf(comparative_data, client_data, base_url)
    
    # Build a clean filename
    safe_name = client.name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_{count}M_SEO_Report.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/count")
def get_report_count(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the total number of snapshots for the client."""
    count = db.execute(
        select(func.count(ReportSnapshot.id)).where(ReportSnapshot.client_id == client_id)
    ).scalar()
    return {"count": count or 0}

@router.get("/latest")
def get_latest_report(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the latest snapshot for the client."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
    ).scalars().first()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    return {
        "id": report.id,
        "client_id": report.client_id,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "status": report.status,
        "snapshot": report.snapshot,
        "narrative": report.narrative,
        "generated_at": report.generated_at,
        "published_at": report.published_at,
        "published_by": report.published_by
    }


@router.get("/{snapshot_id}/pdf")
async def download_single_report_pdf(request: Request, client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Generate and return a PDF of a single report snapshot."""
    snapshot = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
    ).scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")

    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")

    comparative_data = _build_comparative_report([snapshot])

    client_logo_url = client.logo_url
    client_logo_b64 = ""
    if client_logo_url and client_logo_url.strip():
        import httpx
        import base64
        fetch_url = base_url + client_logo_url if client_logo_url.startswith("/") else client_logo_url
        try:
            with httpx.Client(timeout=5.0) as c:
                resp = c.get(fetch_url)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    ctype = resp.headers.get("content-type", "image/png")
                    client_logo_b64 = f"data:{ctype};base64,{b64}"
        except Exception:
            pass

    client_data = {
        "name": client.name,
        "domain": client.domain,
        "logo_url": client.logo_url,
        "logo_b64": client_logo_b64,
        "theme_color": client.theme_color,
    }

    base_url = str(request.base_url).rstrip("/")
    
    # Inject base64 screenshots directly to avoid Playwright network issues
    import base64
    for img in comparative_data.get("screenshots", []):
        file_url = img.get("file_url")
        if file_url:
            parts = file_url.split("/")
            if len(parts) >= 5 and parts[-1] == "image":
                sid = parts[-2]
                s_obj = db.execute(select(Screenshot).where(Screenshot.id == sid)).scalar_one_or_none()
                if s_obj and s_obj.file_data:
                    b64 = base64.b64encode(s_obj.file_data).decode("utf-8")
                    img["base64_data"] = f"data:{s_obj.mime_type or 'image/png'};base64,{b64}"


    from app.services.pdf_service import generate_report_pdf as gen_pdf
    pdf_bytes = await gen_pdf(comparative_data, client_data, base_url)

    safe_name = client.name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_SEO_Report.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{snapshot_id}")
def get_report(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch a specific report by client and id."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    return {
        "id": report.id,
        "client_id": report.client_id,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "status": report.status,
        "snapshot": report.snapshot,
        "narrative": report.narrative,
        "generated_at": report.generated_at,
        "published_at": report.published_at,
        "published_by": report.published_by
    }


# --- Helpers ---

def _resolve_metrics(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date, provider: str) -> dict:
    if provider == "gbp":
        query_start = start_date.replace(day=1)
    else:
        query_start = start_date
        
    metrics = db.execute(
        select(Metric).where(
            Metric.client_id == client_id,
            Metric.provider == provider,
            Metric.captured_on >= query_start,
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
        if key in ["ctr", "position", "avg_session_duration"]:
            val = sums[key][src] / counts[key][src]
            resolved[key] = round(val, 4) if key == "ctr" else round(val, 2)
        else:
            resolved[key] = round(sums[key][src], 2)
                
    return resolved


def _resolve_rankings(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date, prev_start: datetime.date, prev_end: datetime.date) -> dict:
    from app.models.enums import RankingSource
    
    # Fetch all active keywords
    active_keywords = db.execute(
        select(Keyword).where(Keyword.client_id == client_id, Keyword.is_active == True)
    ).scalars().all()
    
    kw_map = {k.id: k for k in active_keywords}
    if not kw_map:
        return {"summary": {}, "keywords": [], "months": []}
        
    rankings = db.execute(
        select(Ranking).where(
            Ranking.keyword_id.in_(kw_map.keys()),
            Ranking.captured_on <= end_date
        ).order_by(Ranking.keyword_id, Ranking.captured_on.asc())
    ).scalars().all()
    
    history_map = {}
    for r in rankings:
        if r.keyword_id not in history_map:
            history_map[r.keyword_id] = []
        history_map[r.keyword_id].append(r)
        
    keywords_list = []
    
    summary = {
        "improved": 0,
        "declined": 0,
        "top_10": 0,
        "11_20": 0,
        "21_50": 0,
        "51_plus": 0
    }
    
    for kw_id, kw in kw_map.items():
        kw_history = history_map.get(kw_id, [])
        initial = kw.initial_rank
        if initial is None and kw_history:
            initial = kw_history[0].position
            
        pos = None
        prev_pos = None
        
        if len(kw_history) >= 1:
            pos = kw_history[-1].position
        if len(kw_history) >= 2:
            prev_pos = kw_history[-2].position
            
        hist_dict = {}
        for r in kw_history[-4:]:
            hist_dict[r.captured_on.strftime("%Y-%m-%d")] = r.position
            
        if pos and prev_pos:
            if pos < prev_pos:
                summary["improved"] += 1
            elif pos > prev_pos:
                summary["declined"] += 1
                
        if pos:
            if pos <= 10:
                summary["top_10"] += 1
            elif pos <= 20:
                summary["11_20"] += 1
            elif pos <= 50:
                summary["21_50"] += 1
            else:
                summary["51_plus"] += 1
                
        change = None
        if initial and pos:
            change = initial - pos
            
        keywords_list.append({
            "keyword_id": str(kw_id),
            "term": kw.term,
            "search_volume": kw.search_volume,
            "initial_rank": initial,
            "history": hist_dict,
            "change": change,
            "position": pos,
            "previous_position": prev_pos
        })
        
    # Sort keyword list so position 1 is at the top
    keywords_list.sort(key=lambda x: x["position"] if x["position"] is not None else 999)

    return {
        "summary": summary,
        "keywords": keywords_list,
        "months": []
    }


def _resolve_ai_visibility(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    month_start = start_date.replace(day=1)
    mentions = db.execute(
        select(AiMention).where(
            AiMention.client_id == client_id,
            AiMention.month >= month_start,
            AiMention.month <= end_date
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
    month_start = start_date.replace(day=1)
    links = db.execute(
        select(Link).where(Link.client_id == client_id, Link.month >= month_start, Link.month <= end_date, Link.status == "active")
    ).scalars().all()
    return [{"id": str(l.id), "url": l.url, "domain": l.domain, "activity_type": l.activity_type, "count": l.count} for l in links]


def _resolve_activities(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    month_start = start_date.replace(day=1)
    activities = db.execute(
        select(Activity).where(Activity.client_id == client_id, Activity.month >= month_start, Activity.month <= end_date)
    ).scalars().all()
    return [{"month": str(a.month), "activity_type": a.activity_type, "count": a.count, "notes": a.notes} for a in activities]


def _resolve_screenshots(db: Session, client_id: uuid.UUID, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    month_start = start_date.replace(day=1)
    screenshots = db.execute(
        select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.month >= month_start, Screenshot.month <= end_date)
    ).scalars().all()
    return [{"month": str(s.month), "file_url": s.file_url, "caption": s.caption} for s in screenshots]


def _compute_kpi_deltas(snapshot: dict, prev_snapshot: dict) -> dict:
    deltas = {}
    for provider in ["gsc", "ga4", "gbp"]:
        deltas[provider] = {}
        for k, v in snapshot[provider].items():
            # Only compute deltas for numeric scalar values, skip lists/dicts (e.g. top_pages)
            if isinstance(v, (int, float)):
                prev_v = prev_snapshot[provider].get(k, 0)
                if isinstance(prev_v, (int, float)):
                    deltas[provider][k] = v - prev_v
    return deltas

def _aggregate_metrics(snapshots, section):
    if not snapshots:
        return {}
        
    count = len(snapshots)
    
    sum_keys = {
        "gsc": ["clicks", "impressions"],
        "ga4": ["sessions", "users", "organic_sessions", "conversions", "ecommerce_events", "revenue"],
        "gbp": ["views", "searches", "interactions", "calls", "direction_requests", "website_clicks", "bookings", "impressions_desktop_maps", "impressions_desktop_search", "impressions_mobile_maps", "impressions_mobile_search"]
    }.get(section, [])
    
    avg_keys = {
        "gsc": ["ctr", "position"],
        "ga4": ["bounce_rate", "session_duration"],
        "gbp": []
    }.get(section, [])
    
    list_keys = {
        "gsc": ["top_pages"],
        "ga4": ["traffic_sources", "devices", "top_pages", "countries"],
        "gbp": []
    }.get(section, [])
    
    list_merge_key = {
        "top_pages": "page",
        "traffic_sources": "source",
        "devices": "device",
        "countries": "country"
    }
    
    list_sum_keys = {
        "top_pages": ["clicks", "impressions", "sessions", "users", "conversions"],
        "traffic_sources": ["sessions", "users", "conversions"],
        "devices": ["sessions", "users", "conversions"],
        "countries": ["sessions", "users", "conversions"]
    }
    
    result = {}
    
    for k in sum_keys + avg_keys:
        result[k] = 0
        
    for s in snapshots:
        data = s.snapshot.get(section, {}) if s.snapshot else {}
        for k in sum_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
        for k in avg_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
            
    if count > 0:
        for k in avg_keys:
            result[k] = result[k] / count
            
    for k in list_keys:
        merged_list = {}
        for s in snapshots:
            data = s.snapshot.get(section, {}) if s.snapshot else {}
            items = data.get(k, [])
            for item in items:
                m_key_name = list_merge_key.get(k)
                m_key = item.get(m_key_name)
                if not m_key:
                    continue
                if m_key not in merged_list:
                    merged_list[m_key] = dict(item)
                else:
                    for sk in list_sum_keys.get(k, []):
                        if sk in item:
                            merged_list[m_key][sk] = merged_list[m_key].get(sk, 0) + item.get(sk, 0)
                            
        for m_key, m_item in merged_list.items():
            if "bounce_rate" in m_item:
                m_item["bounce_rate"] = m_item["bounce_rate"] / count if count > 0 else 0
                
        if list_sum_keys.get(k):
            sort_key = list_sum_keys[k][0]
            result[k] = sorted(merged_list.values(), key=lambda x: x.get(sort_key, 0), reverse=True)
        else:
            result[k] = list(merged_list.values())
            
    return result

def _build_comparative_report(snapshots):
    if not snapshots:
        return {}

    class _Composed:
        """A snapshot with unticked rows already removed.

        Filtering once, here, means every downstream aggregation and the PDF
        template all see the same arrays — there is no second place that could
        forget to apply the composer's choices.
        """

        __slots__ = ("snapshot", "end_date", "narrative")

        def __init__(self, src):
            self.snapshot = composer.apply_selection(src.snapshot or {})
            self.end_date = src.end_date
            self.narrative = getattr(src, "narrative", "") or ""

    snapshots = [_Composed(s) for s in snapshots]
    
    months = []
    for s in snapshots:
        months.append(s.end_date.strftime("%B %Y"))
        
    comparative_data = {
        "months": months,
        "kpi_deltas": {},
        "rankings": {"summary": {}, "keywords": []},
        "links": [],
        "ai_visibility": [],
        "activities": [],
        "screenshots": []
    }
    
    latest_snap = snapshots[-1].snapshot if snapshots[-1].snapshot else {}
    comparative_data["kpi_deltas"] = latest_snap.get("kpi_deltas", {})

    # Carry the composer's choices into the PDF. For a multi-month export the
    # most recent snapshot's selection wins, since that is the one just edited.
    if isinstance(latest_snap.get("included_sections"), dict):
        comparative_data["included_sections"] = latest_snap["included_sections"]
    if isinstance(latest_snap.get("included_items"), dict):
        comparative_data["included_items"] = latest_snap["included_items"]
    comparative_data["narrative"] = snapshots[-1].narrative if getattr(snapshots[-1], 'narrative', None) else ""
    if "rankings" in latest_snap:
        comparative_data["rankings"]["summary"] = latest_snap["rankings"].get("summary", {})
        
    comparative_data["gsc"] = _aggregate_metrics(snapshots, "gsc")
    comparative_data["ga4"] = _aggregate_metrics(snapshots, "ga4")
    comparative_data["gbp"] = _aggregate_metrics(snapshots, "gbp")
        
    kw_map = {}
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        rank_data = snap_data.get("rankings", {}).get("keywords", [])
        for kw in rank_data:
            kid = kw.get("keyword_id")
            if not kid: continue
            if kid not in kw_map:
                kw_map[kid] = {
                    "keyword_id": kid,
                    "term": kw.get("term"),
                    "search_volume": kw.get("search_volume"),
                    "positions": {},
                    "change": None,
                    "initial_rank": kw.get("initial_rank")
                }
            kw_map[kid]["positions"][month] = kw.get("position")
            # Update search_volume if it was previously None
            if kw_map[kid]["search_volume"] is None and kw.get("search_volume"):
                kw_map[kid]["search_volume"] = kw.get("search_volume")
            
    latest_rankings = latest_snap.get("rankings", {}).get("keywords", [])
    for kw in latest_rankings:
        kid = kw.get("keyword_id")
        if kid in kw_map:
            kw_map[kid]["change"] = kw.get("change")
            # Preserve the position order from the latest snapshot
            kw_map[kid]["_sort_pos"] = kw.get("position") or 9999
            
    kw_list = list(kw_map.values())
    kw_list.sort(key=lambda x: x.get("_sort_pos", 9999))
    comparative_data["rankings"]["keywords"] = kw_list
    
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        for item in snap_data.get("links", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["links"].append(item_copy)
        for item in snap_data.get("ai_visibility", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["ai_visibility"].append(item_copy)
        for item in snap_data.get("activities", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["activities"].append(item_copy)
        for item in snap_data.get("screenshots", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["screenshots"].append(item_copy)
            
    # Calculate aggregates for the PDF
    ai_vis = comparative_data["ai_visibility"]
    comparative_data["ai_mentioned"] = sum(1 for m in ai_vis if m.get("mentioned"))
    comparative_data["ai_total"] = len(ai_vis)
    comparative_data["ai_platforms"] = len(set(m.get("platform", "") for m in ai_vis))
    
    ai_by_platform = {}
    for m in ai_vis:
        p = m.get("platform", "unknown")
        if p not in ai_by_platform:
            ai_by_platform[p] = {"mentioned": 0, "total": 0}
        ai_by_platform[p]["total"] += 1
        if m.get("mentioned"):
            ai_by_platform[p]["mentioned"] += 1
    comparative_data["ai_by_platform"] = ai_by_platform
    
    links = comparative_data["links"]
    comparative_data["unique_domains"] = len(set(l.get("domain", "") for l in links))
    link_types = {}
    for l in links:
        t = l.get("activity_type", "Other")
        link_types[t] = link_types.get(t, 0) + 1
    comparative_data["link_types"] = link_types
    
    return comparative_data
