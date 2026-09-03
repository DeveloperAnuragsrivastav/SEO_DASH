from __future__ import annotations
import uuid
import datetime
from pydantic import BaseModel, Field

class KeywordCreate(BaseModel):
    term: str = Field(..., min_length=1)
    fetch_metrics: bool = False

class KeywordResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    term: str
    target_url: str | None = None
    current_rank: int | None = None
    previous_rank: int | None = None
    initial_rank: int | None = None
    is_active: bool
    added_at: datetime.date

    model_config = {"from_attributes": True}
