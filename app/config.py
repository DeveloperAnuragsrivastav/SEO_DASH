from __future__ import annotations
"""Application configuration — all settings from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # ── PostgreSQL (Supabase) ──────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ez_rankings"

    # ── Redis ──────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Celery ─────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── App ────────────────────────────────────────────────────────────
    app_env: str = "development"

    # ── Google Service Account ─────────────────────────────────────────
    google_service_account_json: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ── Groq API ───────────────────────────────────────────────────────
    GROQ_API_KEY: Optional[str] = None

    # DataForSEO Configuration
    DATAFORSEO_MASTER_KEY: str = ""
    DATAFORSEO_LOGIN: str = ""
    DATAFORSEO_PASSWORD: str = ""
    
    # Cost Guardrails
    COST_GUARDRAIL_MULTIPLIER: float = 3.0
    COST_GUARDRAIL_MIN_DAYS: int = 3
    COST_GUARDRAIL_FLOOR_USD: float = 5.0
    
    # ── Webhooks ───────────────────────────────────────────────────────
    webhook_base_url: str = "http://localhost:8000"

    # ── Security ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
