from __future__ import annotations
import uuid
import datetime
from calendar import monthrange
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.database import get_db
from app.models.ai_mention import AiMention
from app.models.ai_prompt import AiPrompt
from app.models.ranking import Ranking
from app.models.keyword import Keyword
from app.dependencies import RequireRole
from app.models.enums import UserRole, AiPlatform
from app.services.ga4_service import get_ai_referrals

router = APIRouter(
    prefix="/clients/{client_id}/ai-visibility",
    tags=["ai_visibility"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

@router.get("/{month_str}")
def get_ai_visibility(client_id: uuid.UUID, month_str: str, db: Session = Depends(get_db)):
    """Fetch AI Visibility data: AI Mentions (Sec 1) and AI Overviews (Sec 2)."""
    try:
        target_month = datetime.datetime.strptime(month_str, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")

    start_date, end_date = get_month_boundaries(target_month.year, target_month.month)

    # --- Section 1: AI Mentions ---
    # Total active prompts
    total_tracked_prompts = db.execute(
        select(func.count(AiPrompt.id)).where(
            AiPrompt.client_id == client_id,
            AiPrompt.is_active == True
        )
    ).scalar() or 0

    # Mentions in month
    mentions = db.execute(
        select(AiMention).where(
            AiMention.client_id == client_id,
            AiMention.captured_on >= start_date,
            AiMention.captured_on <= end_date,
            AiMention.mentioned == True
        )
    ).scalars().all()

    platforms: Dict[str, Dict[str, int]] = {
        platform.value: {"mentions": 0} for platform in AiPlatform
    }

    cited_pages_agg: Dict[str, int] = {}

    for mention in mentions:
        platforms[mention.platform.value]["mentions"] += 1
        if mention.cited_pages:
            for page in mention.cited_pages:
                url = page.get("url")
                if url:
                    cited_pages_agg[url] = cited_pages_agg.get(url, 0) + 1

    cited_pages_list = [
        {"url": url, "mentions": count} for url, count in cited_pages_agg.items()
    ]
    cited_pages_list.sort(key=lambda x: x["mentions"], reverse=True)

    section1 = {
        "total_tracked_prompts": total_tracked_prompts,
        "platforms": platforms,
        "cited_pages": cited_pages_list
    }

    # --- Section 2: AI Overviews ---
    # We want keywords that had ai_overview_present=True at any point in the month
    overview_rankings = db.execute(
        select(Ranking, Keyword.term)
        .join(Keyword, Ranking.keyword_id == Keyword.id)
        .where(
            Keyword.client_id == client_id,
            Ranking.captured_on >= start_date,
            Ranking.captured_on <= end_date,
            Ranking.ai_overview_present == True
        )
        .order_by(Ranking.captured_on.desc())
    ).all()

    # Deduplicate by keyword_id, keeping the most recent position
    seen_keywords = set()
    ai_overview_keywords = []

    for ranking, term in overview_rankings:
        if ranking.keyword_id not in seen_keywords:
            seen_keywords.add(ranking.keyword_id)
            ai_overview_keywords.append({
                "keyword_id": str(ranking.keyword_id),
                "term": term,
                "position": ranking.position
            })

    # Sort alphabetically by term
    ai_overview_keywords.sort(key=lambda x: x["term"])

    section2 = {
        "total_ai_overview_keywords": len(ai_overview_keywords),
        "keywords": ai_overview_keywords
    }

    referrals = get_ai_referrals(db, client_id, start_date, end_date)
    section3 = {
        "ai_referrals": referrals
    }

    return {
        "section1": section1,
        "section2": section2,
        "section3": section3
    }
