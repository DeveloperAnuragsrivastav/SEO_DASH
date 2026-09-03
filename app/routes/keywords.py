from __future__ import annotations
import uuid
import datetime

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.client import Client
from app.models.keyword import Keyword
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, SyncStatus
from app.models.sync_run import SyncRun
from app.schemas.keyword import KeywordCreate, KeywordResponse
from app.services.dataforseo_auth import get_dataforseo_credentials
from app.services.dataforseo_keyword import fetch_keyword_metrics_with_retry

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/keywords",
    tags=["keywords"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

@router.get("", response_model=list[KeywordResponse])
def list_keywords(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """List all active keywords for a client."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from app.models.ranking import Ranking

    keywords = db.execute(
        select(Keyword)
        .where(Keyword.client_id == client_id)
        .where(Keyword.is_active == True)
        .order_by(Keyword.added_at.desc())
    ).scalars().all()
    
    kw_ids = [kw.id for kw in keywords]
    results = []
    if kw_ids:
        rankings = db.execute(
            select(Ranking).where(Ranking.keyword_id.in_(kw_ids)).order_by(Ranking.captured_on.asc())
        ).scalars().all()
        
        hist_map = {kw_id: [] for kw_id in kw_ids}
        for r in rankings:
            hist_map[r.keyword_id].append(r)
            
        for kw in keywords:
            kw_dict = kw.__dict__.copy()
            hist = hist_map[kw.id]
            if hist:
                kw_dict["current_rank"] = hist[-1].position
                kw_dict["target_url"] = hist[-1].url or kw.target_url
                if len(hist) > 1:
                    kw_dict["previous_rank"] = hist[-2].position
            results.append(kw_dict)
        return results

    return [kw.__dict__ for kw in keywords]


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
def create_keyword(
    client_id: uuid.UUID, keyword_in: KeywordCreate, db: Session = Depends(get_db)
):
    """
    Creates a keyword.
    """
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if keyword_in.fetch_metrics:
        conn = db.query(Connection).filter(
            Connection.client_id == client_id,
            Connection.provider == ProviderType.dataforseo,
            Connection.status == ConnectionStatus.connected
        ).first()

        if conn:
            try:
                login, password = get_dataforseo_credentials(db, conn.id)
                metrics = fetch_keyword_metrics_with_retry(login, password, keyword_in.term)
                
                # Log successful sync_run
                sync_run = SyncRun(
                    client_id=client_id,
                    provider="dataforseo",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    finished_at=datetime.datetime.now(datetime.timezone.utc),
                    status=SyncStatus.success,
                    cost=metrics.get("cost", 0.0)
                )
                db.add(sync_run)
                db.commit()
            except Exception as e:
                # Log failed sync_run
                sync_run = SyncRun(
                    client_id=client_id,
                    provider="dataforseo",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    finished_at=datetime.datetime.now(datetime.timezone.utc),
                    status=SyncStatus.failed,
                    error=str(e)
                )
                db.add(sync_run)
                db.commit()
                # Don't raise an error here, allow the keyword to be saved.

    keyword = Keyword(
        client_id=client_id,
        term=keyword_in.term,
        is_active=True,
        added_at=datetime.date.today()
    )
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    
    return keyword

@router.put("/{keyword_id}", response_model=KeywordResponse)
def update_keyword(
    client_id: uuid.UUID, keyword_id: uuid.UUID, is_active: bool, db: Session = Depends(get_db)
):
    """Deactivate or reactivate a keyword."""
    keyword = db.execute(
        select(Keyword).where(Keyword.client_id == client_id, Keyword.id == keyword_id)
    ).scalar_one_or_none()
    
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    keyword.is_active = is_active
    db.commit()
    db.refresh(keyword)
    return keyword


@router.post("/upload_csv", status_code=status.HTTP_201_CREATED)
def upload_keywords_csv(
    client_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    if not (file.filename.endswith(".csv") or file.filename.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Must be a CSV or Excel file")
    
    rows = []
    raw_headers = []
    
    if file.filename.endswith(".xlsx"):
        import openpyxl
        content = file.file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        if not ws or ws.max_row < 1:
            raise HTTPException(status_code=400, detail="Empty Excel file")
        raw_headers = [str(c.value).strip() if c.value else "" for c in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            row_dict = {}
            for k, v in zip(raw_headers, row):
                row_dict[k] = v
            rows.append(row_dict)
    else:
        content = file.file.read().decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        header_row = next(reader, None)
        if not header_row:
            raise HTTPException(status_code=400, detail="Empty CSV")
        raw_headers = [c.strip() for c in header_row]
        for row in reader:
            row_dict = {}
            for k, v in zip(raw_headers, row):
                row_dict[k] = v
            rows.append(row_dict)
        
    normalized_headers = [h.lower().replace(" ", "_") for h in raw_headers]
    
    # Check for keyword column
    if "keyword" not in normalized_headers and "term" not in normalized_headers:
        raise HTTPException(status_code=400, detail="CSV/Excel must contain 'Keyword' column")
        
    # Extract dynamic month columns (e.g. "Aug'26")
    import re
    from datetime import datetime
    month_cols = []
    for h in raw_headers:
        norm_h = h.lower().replace(" ", "_")
        if norm_h not in ["keyword", "term", "sv", "search_volume", "initial_ranking", "initial_rank", "group_tag", "target_url", "url", "current_rank"]:
            if "'" in h:
                try:
                    dt = datetime.strptime(h, "%b'%y")
                    month_cols.append({"header": h, "date": dt.date()})
                except ValueError:
                    pass

    success_count = 0
    errors = []
    
    for row_num, row in enumerate(rows, start=2):
        row_norm = {k.lower().replace(" ", "_"): v for k, v in row.items() if k}
        try:
            term = str(row_norm.get("term") or row_norm.get("keyword") or "").strip()
            if not term or term == "None":
                continue
                
            group_tag = str(row_norm.get("group_tag") or "").strip()
            group_tag = group_tag if group_tag and group_tag != "None" else None
            target_url = str(row_norm.get("target_url") or row_norm.get("url") or "").strip()
            target_url = target_url if target_url and target_url != "None" else None
            
            sv_str = str(row_norm.get("sv") or row_norm.get("search_volume") or "").strip()
            sv = int(float(sv_str)) if sv_str and sv_str != "-" and sv_str != "None" else None
            
            initial_str = str(row_norm.get("initial_ranking") or row_norm.get("initial_rank") or "").strip()
            initial_rank = int(float(initial_str)) if initial_str and initial_str != "-" and initial_str != "None" else None
            
            stmt = select(Keyword).where(
                Keyword.client_id == client_id,
                Keyword.term == term
            )
            existing = db.execute(stmt).scalar_one_or_none()
            
            kw_id = None
            if existing:
                existing.group_tag = group_tag or existing.group_tag
                existing.target_url = target_url or existing.target_url
                existing.is_active = True
                if sv is not None:
                    existing.search_volume = sv
                if existing.initial_rank is None and initial_rank is not None:
                    existing.initial_rank = initial_rank
                kw_id = existing.id
            else:
                new_kw = Keyword(
                    client_id=client_id,
                    term=term,
                    group_tag=group_tag,
                    target_url=target_url,
                    search_volume=sv,
                    initial_rank=initial_rank,
                    is_active=True,
                    added_at=datetime.today().date()
                )
                db.add(new_kw)
                db.flush()
                kw_id = new_kw.id
            
            # Process dynamic month columns
            from app.models.ranking import Ranking
            from app.models.enums import RankingSource
            
            for m_col in month_cols:
                rank_val = str(row.get(m_col["header"]) or "").strip()
                if rank_val and rank_val != "-" and rank_val != "None":
                    rank_pos = int(float(rank_val))
                    existing_r = db.execute(
                        select(Ranking).where(Ranking.keyword_id == kw_id, Ranking.captured_on == m_col["date"])
                    ).scalar_one_or_none()
                    
                    if existing_r:
                        existing_r.position = rank_pos
                        existing_r.source = RankingSource.manual
                    else:
                        db.add(Ranking(
                            keyword_id=kw_id,
                            captured_on=m_col["date"],
                            position=rank_pos,
                            source=RankingSource.manual
                        ))
            
            # Also handle old 'current_rank' column just in case
            curr_str = str(row_norm.get("current_rank") or "").strip()
            if curr_str and curr_str != "-" and curr_str != "None":
                curr_rank = int(float(curr_str))
                target_date = datetime.date.today()
                existing_r = db.execute(
                    select(Ranking).where(Ranking.keyword_id == kw_id, Ranking.captured_on == target_date)
                ).scalar_one_or_none()
                if existing_r:
                    existing_r.position = curr_rank
                    existing_r.source = RankingSource.manual
                else:
                    db.add(Ranking(
                        keyword_id=kw_id,
                        captured_on=target_date,
                        position=curr_rank,
                        source=RankingSource.manual
                    ))
                    
            success_count += 1
        except Exception as e:
            errors.append({"row": row_num, "error": str(e)})
            
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error saving data: {str(e)}")

    return {"status": "success", "rows_processed": success_count, "errors": errors}

@router.get("/history")
def get_keyword_history(client_id: uuid.UUID, page: int = 1, page_size: int = 25, db: Session = Depends(get_db)):
    """Fetch pivoted monthly history for all keywords of a client."""
    from sqlalchemy import func
    
    # Base query for active keywords
    base_query = select(Keyword).where(Keyword.client_id == client_id, Keyword.is_active == True)
    
    # Get total count
    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0
    
    # Fetch paginated keywords
    keywords = db.execute(
        base_query.order_by(Keyword.term).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    
    if not keywords:
        return {"items": [], "total": total, "page": page, "page_size": page_size}
        
    kw_ids = [k.id for k in keywords]
    
    # Fetch all manual rankings for these keywords
    from app.models.ranking import Ranking
    from app.models.enums import RankingSource
    
    rankings = db.execute(
        select(Ranking).where(
            Ranking.keyword_id.in_(kw_ids)
        )
    ).scalars().all()
    
    # Build history map
    history_map = {}
    for r in rankings:
        if r.keyword_id not in history_map:
            history_map[r.keyword_id] = {}
        month_str = r.captured_on.strftime("%b'%y") # Format: Aug'26
        history_map[r.keyword_id][month_str] = r.position
        
    result = []
    for k in keywords:
        hist = history_map.get(k.id, {})
        initial = k.initial_rank
        if initial is None and hist:
            earliest_month = min(hist.keys())
            initial = hist[earliest_month]
            
        result.append({
            "id": str(k.id),
            "keyword": k.term,
            "search_volume": k.search_volume,
            "initial_rank": initial,
            "history": hist
        })
        
    return {"items": result, "total": total, "page": page, "page_size": page_size}
