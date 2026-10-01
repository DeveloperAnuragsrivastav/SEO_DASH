from __future__ import annotations
"""Alembic env.py — reads DATABASE_URL from environment, imports all models."""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

load_dotenv()

# Alembic Config object
config = context.config

# Override sqlalchemy.url from environment if not already set dynamically
# (conftest.py sets it explicitly for the test DB)
current_url = config.get_main_option("sqlalchemy.url")
if not current_url or current_url.startswith("driver://"):
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url[len("postgres://"):]
        # "%" is special to the ini parser; a password may contain one.
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so their metadata is registered on Base
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402, F401
    Account,
    Activity,
    AiMention,
    AiPrompt,
    Client,
    ClientSection,
    Connection,
    Keyword,
    Link,
    Metric,
    ProviderTask,
    Ranking,
    ReportSnapshot,
    Screenshot,
    SyncRun,
    User,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
