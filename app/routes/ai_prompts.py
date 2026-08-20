from __future__ import annotations
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_prompt import AiPrompt
from app.models.client import Client
from app.schemas.ai_prompt import AIPromptCreate, AIPromptResponse, AIPromptUpdate

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/ai_prompts",
    tags=["ai_prompts"],
    dependencies=[Depends(RequireRole([UserRole.agency_admin, UserRole.agency_staff]))]
)

@router.get("", response_model=list[AIPromptResponse])
def list_ai_prompts(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """List active AI prompts for a client."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    prompts = db.execute(
        select(AiPrompt)
        .where(AiPrompt.client_id == client_id)
        .where(AiPrompt.is_active == True)
        .order_by(AiPrompt.added_at.desc())
    ).scalars().all()
    
    return list(prompts)


@router.post("", response_model=AIPromptResponse, status_code=status.HTTP_201_CREATED)
def create_ai_prompt(
    client_id: uuid.UUID, prompt_in: AIPromptCreate, db: Session = Depends(get_db)
):
    """Create a new AI prompt for a client."""
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    prompt = AiPrompt(
        client_id=client_id,
        prompt_text=prompt_in.prompt_text,
        is_active=True,
        added_at=datetime.date.today()
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.put("/{prompt_id}", response_model=AIPromptResponse)
def update_ai_prompt(
    client_id: uuid.UUID, prompt_id: uuid.UUID, prompt_in: AIPromptUpdate, db: Session = Depends(get_db)
):
    """Update or deactivate an AI prompt."""
    prompt = db.execute(
        select(AiPrompt).where(AiPrompt.client_id == client_id, AiPrompt.id == prompt_id)
    ).scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="AI Prompt not found")

    if prompt_in.prompt_text is not None:
        prompt.prompt_text = prompt_in.prompt_text
    if prompt_in.is_active is not None:
        prompt.is_active = prompt_in.is_active

    db.commit()
    db.refresh(prompt)
    return prompt
