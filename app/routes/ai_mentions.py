from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_mention import AiMention
from app.models.client import Client
from app.models.enums import AiMentionSource
from app.schemas.ai_mention import AIMentionManualCreate, AIMentionResponse

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/ai_mentions",
    tags=["ai_mentions"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

@router.post("/manual", response_model=AIMentionResponse, status_code=status.HTTP_201_CREATED)
def create_manual_ai_mention(
    client_id: uuid.UUID, mention_in: AIMentionManualCreate, db: Session = Depends(get_db)
):
    """Manually enter an AI mention record for a client."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    mention = AiMention(
        client_id=client_id,
        prompt_id=mention_in.prompt_id,
        platform=mention_in.platform,
        captured_on=mention_in.captured_on,
        mentioned=mention_in.mentioned,
        cited_pages=[page.model_dump() for page in mention_in.cited_pages] if mention_in.cited_pages else None,
        source=AiMentionSource.manual,
        raw_response=None
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)
    return mention

@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk_ai_mentions(
    client_id: uuid.UUID, mentions_in: list[AIMentionManualCreate], db: Session = Depends(get_db)
):
    """Manually enter multiple AI mention records via bulk upload."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    mentions = []
    for mention_in in mentions_in:
        mention = AiMention(
            client_id=client_id,
            prompt_id=mention_in.prompt_id,
            platform=mention_in.platform,
            captured_on=mention_in.captured_on,
            mentioned=mention_in.mentioned,
            cited_pages=[page.model_dump() for page in mention_in.cited_pages] if mention_in.cited_pages else None,
            source=AiMentionSource.manual,
            raw_response=None
        )
        mentions.append(mention)

    if mentions:
        db.add_all(mentions)
        db.commit()

    return {"status": "success", "rows_inserted": len(mentions)}
