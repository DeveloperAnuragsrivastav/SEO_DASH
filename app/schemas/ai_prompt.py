from __future__ import annotations
import uuid
import datetime
from pydantic import BaseModel, Field

class AIPromptCreate(BaseModel):
    prompt_text: str = Field(..., min_length=1)

class AIPromptUpdate(BaseModel):
    prompt_text: str | None = Field(None, min_length=1)
    is_active: bool | None = None

class AIPromptResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    prompt_text: str
    is_active: bool
    added_at: datetime.date

    model_config = {"from_attributes": True}
