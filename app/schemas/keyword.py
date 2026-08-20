from __future__ import annotations
from typing import Optional
import uuid
import datetime
from pydantic import BaseModel, Field

class KeywordCreate(BaseModel):
    term: str = Field(..., min_length=1)
    search_volume: Optional[int] = None
    fetch_metrics: bool = False

class KeywordResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    term: str
    search_volume: Optional[int]
    is_active: bool
    added_at: datetime.date

    model_config = {"from_attributes": True}
