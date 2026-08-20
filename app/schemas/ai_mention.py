from __future__ import annotations
from typing import Optional
import uuid
import datetime
from pydantic import BaseModel
from app.models.enums import AiPlatform

class PageCitation(BaseModel):
    page: str
    prompt_count: int = 1

class AIMentionManualCreate(BaseModel):
    prompt_id: Optional[uuid.UUID] = None
    platform: AiPlatform
    captured_on: datetime.date
    mentioned: bool
    cited_pages: list[PageCitation] | None = None

class AIMentionResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    prompt_id: Optional[uuid.UUID]
    platform: AiPlatform
    captured_on: datetime.date
    mentioned: bool
    cited_pages: list[dict] | None
    source: str
    raw_response: Optional[str]

    model_config = {"from_attributes": True}
