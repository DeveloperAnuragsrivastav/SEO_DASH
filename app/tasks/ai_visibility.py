from __future__ import annotations
import logging
from datetime import datetime, timezone.utc
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.ai_mention import AiMention
from app.models.ai_prompt import AiPrompt
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AiPlatform, AiMentionSource, ConnectionStatus, ProviderType, SyncStatus
from app.models.sync_run import SyncRun
from app.services.dataforseo_auth import get_dataforseo_credentials
from app.services.groq_service import extract_mention_and_citations
from app.tasks.rankings import alert_agency

logger = logging.getLogger(__name__)

PLATFORMS = {
    AiPlatform.chatgpt: "chat_gpt",
    AiPlatform.claude: "claude",
    AiPlatform.gemini: "gemini",
    AiPlatform.perplexity: "perplexity"
}

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def _post_llm_responses_live_with_retry(login: str, password: str, platform_key: str, payload: dict) -> dict:
    url = f"https://api.dataforseo.com/v3/ai_optimization/{platform_key}/llm_responses/live"
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            url,
            auth=(login, password),
            json=[payload]
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status_code") == 20000:
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                return tasks[0]["result"][0], data.get("cost", 0.0)
        
        raise Exception(f"DataForSEO error: {data.get('status_message', 'Unknown error')}")

def _process_ai_visibility(db: Session, conn: Connection):
    client = db.execute(select(Client).where(Client.id == conn.client_id)).scalar_one()
    
    sync_run = SyncRun(
        client_id=conn.client_id,
        provider="dataforseo",
        started_at=datetime.now(timezone.utc),
        status=SyncStatus.partial,
        rows=0,
    )
    db.add(sync_run)
    db.commit()

    try:
        login, password = get_dataforseo_credentials(db, conn.id)
        
        prompts = db.execute(
            select(AiPrompt)
            .where(AiPrompt.client_id == conn.client_id, AiPrompt.is_active == True)
        ).scalars().all()

        if not prompts:
            sync_run.status = SyncStatus.success
            sync_run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        total_mentions_written = 0
        total_cost = 0.0

        for prompt in prompts:
            for platform_enum, dfs_platform_key in PLATFORMS.items():
                payload = {
                    "user_prompt": prompt.prompt_text,
                    "temperature": 0.7,
                    "web_search": True
                }

                try:
                    result, cost = _post_llm_responses_live_with_retry(login, password, dfs_platform_key, payload)
                    raw_content = result.get("content", "")
                    
                    # Run Groq extraction
                    extracted = extract_mention_and_citations(raw_content, client.domain, client.name)
                    
                    mention_record = AiMention(
                        client_id=client.id,
                        prompt_id=prompt.id,
                        platform=platform_enum,
                        captured_on=datetime.now(timezone.utc).date(),
                        mentioned=extracted.get("mentioned", False),
                        cited_pages=extracted.get("cited_pages", []),
                        source=AiMentionSource.llm_responses_custom,
                        raw_response=raw_content
                    )
                    db.add(mention_record)
                    total_mentions_written += 1
                    total_cost += cost
                except Exception as e:
                    logger.error(f"Failed to fetch or parse LLM response for {dfs_platform_key}: {e}")
                    raise e
                    
        db.commit()

        sync_run.status = SyncStatus.success
        sync_run.rows = total_mentions_written
        sync_run.cost = total_cost
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        conn.status = ConnectionStatus.error
        error_msg = f"AI Visibility pull failed: {str(e)}"
        conn.last_error = error_msg
        
        sync_run.status = SyncStatus.failed
        sync_run.error = str(e)
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        
        alert_agency(conn.id, error_msg)
        raise e

@celery_app.task(name="trigger_ai_visibility_pull_on_demand")
def trigger_ai_visibility_pull_on_demand():
    """
    Job to pull AI visibility for all clients with DataForSEO.
    Intended to be triggered on-demand (e.g. during report generation) rather than on a schedule.
    """
    with SessionLocal() as db:
        connections = db.execute(
            select(Connection)
            .where(Connection.provider == ProviderType.dataforseo)
            .where(Connection.status == ConnectionStatus.connected)
        ).scalars().all()

        for conn in connections:
            try:
                _process_ai_visibility(db, conn)
            except Exception as e:
                logger.error(f"Error processing AI Visibility for connection {conn.id}: {e}")
