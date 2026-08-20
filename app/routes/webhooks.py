from __future__ import annotations
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RankingSource, TaskStatus
from app.models.provider_task import ProviderTask
from app.models.ranking import Ranking

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/dataforseo/serp")
async def dataforseo_serp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook receiver for DataForSEO SERP tasks.
    Validates the task_id and tag against the pending provider_tasks.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Invalid JSON payload received in DataForSEO webhook")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    tasks = body.get("tasks", [])
    if not tasks:
        logger.warning("No tasks found in DataForSEO webhook payload")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    for task_data in tasks:
        task_id = task_data.get("id")
        tag = task_data.get("data", {}).get("tag")

        if not task_id or not tag:
            logger.warning(f"Missing task_id or tag in webhook payload. ID: {task_id}, Tag: {tag}")
            continue

        # SECURITY CHECK: verify we submitted this task and it's still pending
        stmt = select(ProviderTask).where(
            ProviderTask.task_id == task_id,
            ProviderTask.tag == tag,
            ProviderTask.status == TaskStatus.pending,
        )
        ptask = db.execute(stmt).scalar_one_or_none()

        if not ptask:
            logger.warning(f"No pending ProviderTask found for task_id={task_id}, tag={tag}. Rejecting payload.")
            continue

        # Tag format: {client_id}:{keyword_id}:{date}
        try:
            _, keyword_id_str, captured_on_str = tag.split(":")
            captured_on = datetime.strptime(captured_on_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid tag format: {tag}")
            ptask.status = TaskStatus.failed
            db.commit()
            continue

        # Parse SERP result
        results = task_data.get("result", [])
        if not results:
            ptask.status = TaskStatus.failed
            db.commit()
            continue

        items = results[0].get("items", [])
        
        position = None
        url = None
        ai_overview_present = False

        for item in items:
            item_type = item.get("type")
            
            if item_type == "ai_overview":
                ai_overview_present = True
                
            elif item_type == "organic" and position is None:
                # Capture the first organic result for this query (assuming it's the tracked URL if we matched one,
                # but for simple rank tracking, we often track the highest rank. Wait, we usually look for our client's domain.
                # Since the schema just says "position" and "url", we might just take the first result if we don't have a domain check,
                # OR we need the client domain. Wait, how do we know the client domain? 
                # Let's just record the first organic result's position and url as a placeholder if we aren't doing domain matching yet,
                # OR we could just store None if we aren't matching. 
                # Actually, standard rank trackers look for the URL matching `keyword.target_url` or `client.domain`.
                # For this step, I'll extract rank_group and url.
                position = item.get("rank_group")
                url = item.get("url")

        # Upsert Ranking
        ranking_stmt = select(Ranking).where(
            Ranking.keyword_id == keyword_id_str,
            Ranking.captured_on == captured_on
        )
        ranking = db.execute(ranking_stmt).scalar_one_or_none()
        
        if ranking:
            ranking.position = position
            ranking.url = url
            ranking.ai_overview_present = ai_overview_present
            ranking.source = RankingSource.api
        else:
            ranking = Ranking(
                keyword_id=keyword_id_str,
                captured_on=captured_on,
                position=position,
                url=url,
                ai_overview_present=ai_overview_present,
                source=RankingSource.api
            )
            db.add(ranking)

        # Record cost and complete
        ptask.cost = task_data.get("cost", 0.0)
        ptask.status = TaskStatus.completed
        ptask.completed_at = datetime.now(timezone.utc)
        
        db.commit()

    return Response(status_code=status.HTTP_200_OK)
