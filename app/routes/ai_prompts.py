from __future__ import annotations
import uuid
import datetime
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
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
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

@router.get("")
def list_ai_prompts(client_id: uuid.UUID, page: int = 1, page_size: int = 25, db: Session = Depends(get_db)):
    """List active AI prompts for a client."""
    from sqlalchemy import func
    client = db.execute(select(Client).where(Client.id == client_id)).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    base_query = (
        select(AiPrompt)
        .where(AiPrompt.client_id == client_id)
        .where(AiPrompt.is_active == True)
    )

    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0

    prompts = db.execute(
        base_query.order_by(AiPrompt.added_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    
    return {"items": list(prompts), "total": total, "page": page, "page_size": page_size}


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


@router.post("/upload_csv", status_code=status.HTTP_201_CREATED)
def upload_ai_prompts_csv(
    client_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Must be a CSV file")
    
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV")
        
    required_cols = {"prompt_text"}
    actual_cols = {col.lower() for col in reader.fieldnames}
    if not required_cols.issubset(actual_cols):
        raise HTTPException(status_code=400, detail=f"CSV must contain columns: {', '.join(required_cols)}")
        
    prompts_to_insert = []
    success_count = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            prompt_text = row.get("prompt_text", "").strip()
            if not prompt_text:
                continue
            
            stmt = select(AiPrompt).where(
                AiPrompt.client_id == client_id,
                AiPrompt.prompt_text == prompt_text
            )
            existing = db.execute(stmt).scalar_one_or_none()
            
            if existing:
                existing.is_active = True
            else:
                prompts_to_insert.append(
                    AiPrompt(
                        client_id=client_id,
                        prompt_text=prompt_text,
                        is_active=True,
                        added_at=datetime.date.today()
                    )
                )
            success_count += 1
        except Exception as e:
            errors.append({"row": row_num, "error": str(e)})
            
    if prompts_to_insert:
        db.add_all(prompts_to_insert)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
        
    return {"status": "success", "rows_processed": success_count, "errors": errors}
