from __future__ import annotations
"""Health-check routes — liveness and readiness. §14.

Two distinct routes, not one combined endpoint:
  /health/live  — confirms the process is up
  /health/ready — confirms Postgres connectivity via an actual query
"""



from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, str]:
    """Liveness probe — process is up and serving requests."""
    return {"status": "ok"}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness probe — Postgres connectivity confirmed via actual query."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
