from __future__ import annotations
from typing import Optional
"""PostgreSQL native ENUM types — one per enum in architecture.md §11.

These are used by both SQLAlchemy models and Alembic migrations.
Created as actual PG ENUM types, not CHECK constraints.
"""

import enum


# ── users.role ─────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    manager = "manager"
    user = "user"



# ── clients.status ─────────────────────────────────────────────────────
class ClientStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    churned = "churned"


# ── connections.provider ───────────────────────────────────────────────
class ProviderType(str, enum.Enum):
    gsc = "gsc"
    ga4 = "ga4"
    gbp = "gbp"
    dataforseo = "dataforseo"


# ── connections.access_mode ────────────────────────────────────────────
class AccessMode(str, enum.Enum):
    platform_shared = "platform_shared"
    client_owned = "client_owned"


# ── connections.status ─────────────────────────────────────────────────
class ConnectionStatus(str, enum.Enum):
    connected = "connected"
    error = "error"
    expired = "expired"
    not_connected = "not_connected"


# ── rankings.source ───────────────────────────────────────────────────
class RankingSource(str, enum.Enum):
    api = "api"
    manual = "manual"


# ── provider_tasks.status ─────────────────────────────────────────────
class TaskStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


# ── ai_mentions.platform ──────────────────────────────────────────────
class AiPlatform(str, enum.Enum):
    chatgpt = "chatgpt"
    claude = "claude"
    gemini = "gemini"
    perplexity = "perplexity"
    grok = "grok"
    google_ai_overview = "google_ai_overview"


# ── ai_mentions.source ────────────────────────────────────────────────
class AiMentionSource(str, enum.Enum):
    llm_responses_custom = "llm_responses_custom"
    manual = "manual"


# ── metrics.source ────────────────────────────────────────────────────
class MetricSource(str, enum.Enum):
    api = "api"
    manual = "manual"


# ── links.status ──────────────────────────────────────────────────────
class LinkStatus(str, enum.Enum):
    active = "active"
    removed = "removed"
    pending = "pending"


# ── report_months.status ──────────────────────────────────────────────
class ReportStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    published = "published"


# ── sync_runs.status ──────────────────────────────────────────────────
class SyncStatus(str, enum.Enum):
    success = "success"
    partial = "partial"
    failed = "failed"
