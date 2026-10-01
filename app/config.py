"""Application configuration — all settings from environment variables."""

from __future__ import annotations
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # ── PostgreSQL (Supabase) ──────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ez_rankings"

    # ── Uploads ────────────────────────────────────────────────────────
    # Largest image accepted anywhere (screenshots, cover, logos), and the
    # largest request body of any kind — a sheet or a handful of images.
    MAX_IMAGE_MB: int = 5
    MAX_REQUEST_MB: int = 12

    # ── App ────────────────────────────────────────────────────────────
    app_env: str = "development"

    # ── Google Service Account ─────────────────────────────────────────
    google_service_account_json: str | None = None
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    # ── OpenAI API ───────────────────────────────────────────────────────
    OPENAI_API_KEY: str | None = None

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

    # ── Agency identity ────────────────────────────────────────────────
    # Printed on every report. Kept here rather than in the template so a
    # rename, a new contact address or a different partner line is a config
    # change, not a code change.
    AGENCY_NAME: str = "EZ Rankings"
    AGENCY_TAGLINE: str = "AI-enabled digital marketing partner"
    AGENCY_CONTACT_EMAIL: str = "contact@ezrankings.com"
    AGENCY_CONTACT_LINE: str = "Let’s discuss next month’s targets"

    # ── Security ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("database_url")
    @classmethod
    def _sqlalchemy_scheme(cls, v: str) -> str:
        # Railway and Heroku hand out "postgres://", which SQLAlchemy 2 refuses.
        return "postgresql://" + v[len("postgres://"):] if v.startswith("postgres://") else v


settings = Settings()
