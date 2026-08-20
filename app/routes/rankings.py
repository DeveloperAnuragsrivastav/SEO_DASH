from __future__ import annotations
from typing import Optional
import csv
import io
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RankingSource
from app.models.keyword import Keyword
from app.models.ranking import Ranking

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/rankings",
    tags=["rankings"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)


class ManualRankingInput(BaseModel):
    keyword_id: uuid.UUID
    captured_on: date
    position: Optional[int] = Field(None, ge=1)
    url: Optional[str] = None


from datetime import timedelta
from app.models.screenshot import Screenshot

@router.get("/{month_str}")
def get_rankings(
    client_id: uuid.UUID,
    month_str: str,
    db: Session = Depends(get_db),
) -> dict:
    """Fetch rankings for a client for a given month with 90-day history."""
    target_date = datetime.strptime(month_str, "%Y-%m").date()
    
    # We define the 'current' period as the month in question.
    # We want the position as of the end of the target month (or the latest available in that month).
    import calendar
    _, last_day = calendar.monthrange(target_date.year, target_date.month)
    month_end = date(target_date.year, target_date.month, last_day)
    
    history_start = month_end - timedelta(days=90)
    
    keywords = db.execute(select(Keyword).where(Keyword.client_id == client_id)).scalars().all()
    if not keywords:
        return {"data": []}
        
    kw_ids = [kw.id for kw in keywords]
    
    rankings_raw = db.execute(
        select(Ranking).where(Ranking.keyword_id.in_(kw_ids), Ranking.captured_on >= history_start, Ranking.captured_on <= month_end).order_by(Ranking.captured_on.asc())
    ).scalars().all()
    
    # Also fetch the "best" rank ever
    # Group by keyword_id to find min(position)
    from sqlalchemy import func
    best_ranks = db.execute(
        select(Ranking.keyword_id, func.min(Ranking.position)).where(Ranking.keyword_id.in_(kw_ids)).group_by(Ranking.keyword_id)
    ).all()
    best_map = {row[0]: row[1] for row in best_ranks}
    
    screenshots_raw = db.execute(
        select(Screenshot).where(Screenshot.client_id == client_id, Screenshot.month == target_date, Screenshot.keyword_id.isnot(None))
    ).scalars().all()
    ss_map = {s.keyword_id: s.file_url for s in screenshots_raw}

    # Group rankings by keyword_id
    history_by_kw = {kw.id: [] for kw in keywords}
    for r in rankings_raw:
        history_by_kw[r.keyword_id].append(r)
        
    results = []
    for kw in keywords:
        hist = history_by_kw[kw.id]
        if not hist:
            continue
            
        current_ranking = hist[-1]
        current_pos = current_ranking.position
        source = current_ranking.source.value if current_ranking.source else "api"
        
        # previous position (latest position before the current month, or the first in the month if we only have data in the month)
        # Actually, let's just use the position from exactly 30 days ago, or the earliest in the history
        prev_pos = None
        for r in reversed(hist):
            if r.captured_on < target_date:
                prev_pos = r.position
                break
        if prev_pos is None and len(hist) > 1:
            prev_pos = hist[0].position
            
        change = None
        if current_pos is not None and prev_pos is not None:
            # Change is positive if rank improved (i.e., position decreased)
            change = prev_pos - current_pos
            
        history_points = [
            {"date": r.captured_on.isoformat(), "position": r.position}
            for r in hist
        ]
        
        results.append({
            "keyword_id": kw.id,
            "term": kw.term,
            "group_tag": kw.group_tag,
            "current_position": current_pos,
            "previous_position": prev_pos,
            "best_position": best_map.get(kw.id),
            "change": change,
            "history": history_points,
            "source": source,
            "screenshot": ss_map.get(kw.id)
        })
        
    return {"data": results}


@router.post("/manual", status_code=201)
def create_manual_ranking(
    client_id: uuid.UUID,
    data: ManualRankingInput,
    db: Session = Depends(get_db),
) -> dict:
    """Manually enter a single ranking."""
    keyword = db.get(Keyword, data.keyword_id)
    if not keyword or keyword.client_id != client_id:
        raise HTTPException(status_code=404, detail="Keyword not found for this client")

    ranking_stmt = select(Ranking).where(
        Ranking.keyword_id == data.keyword_id, Ranking.captured_on == data.captured_on
    )
    ranking = db.execute(ranking_stmt).scalar_one_or_none()

    if ranking:
        ranking.position = data.position
        ranking.url = data.url
        ranking.source = RankingSource.manual
    else:
        ranking = Ranking(
            keyword_id=data.keyword_id,
            captured_on=data.captured_on,
            position=data.position,
            url=data.url,
            ai_overview_present=None,
            source=RankingSource.manual,
        )
        db.add(ranking)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return {"status": "success"}


@router.post("/upload_csv", status_code=201)
def upload_rankings_csv(
    client_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload a CSV of rankings.
    Expected columns: keyword, position, date, url
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Must be a CSV file")

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV")

    required_cols = {"keyword", "position", "date", "url"}
    actual_cols = {col.lower() for col in reader.fieldnames}
    if not required_cols.issubset(actual_cols):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {', '.join(required_cols)}",
        )

    # Pre-fetch active keywords for this client to match by term
    client_keywords = db.execute(
        select(Keyword).where(Keyword.client_id == client_id)
    ).scalars().all()
    keyword_map = {kw.term.lower(): kw for kw in client_keywords}

    success_count = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        term = row.get("keyword", "").strip()
        position_str = row.get("position", "").strip()
        date_str = row.get("date", "").strip()
        url = row.get("url", "").strip() or None

        if not term or not date_str:
            errors.append({"row": row_num, "error": "Missing keyword or date"})
            continue

        kw = keyword_map.get(term.lower())
        if not kw:
            errors.append({"row": row_num, "error": f"Keyword '{term}' not tracked for this client"})
            continue

        try:
            captured_on = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            errors.append({"row": row_num, "error": f"Invalid date format '{date_str}', expected YYYY-MM-DD"})
            continue

        position = None
        if position_str:
            try:
                position = int(position_str)
                if position < 1:
                    raise ValueError
            except ValueError:
                errors.append({"row": row_num, "error": f"Invalid position '{position_str}', expected positive integer"})
                continue

        # Upsert
        ranking_stmt = select(Ranking).where(
            Ranking.keyword_id == kw.id, Ranking.captured_on == captured_on
        )
        ranking = db.execute(ranking_stmt).scalar_one_or_none()

        if ranking:
            ranking.position = position
            ranking.url = url
            ranking.source = RankingSource.manual
        else:
            ranking = Ranking(
                keyword_id=kw.id,
                captured_on=captured_on,
                position=position,
                url=url,
                ai_overview_present=None,
                source=RankingSource.manual,
            )
            db.add(ranking)

        success_count += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    return {
        "status": "partial" if errors and success_count else ("success" if success_count else "failed"),
        "rows_inserted": success_count,
        "errors": errors,
    }
