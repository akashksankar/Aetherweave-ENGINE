"""
Alembic Migration Environment
==============================

Configures Alembic to use SQLAlchemy's async engine so migrations run
on the same asyncpg connection as the application.

Key pattern:
  - `run_migrations_online()` uses `asyncio.run()` to drive the async context.
  - `target_metadata` points to our SQLAlchemy Base so Alembic auto-detects models.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── Import Base AFTER registering all models ──────────────────────────────────
# This ensures all ORM models are mapped before Alembic reads metadata.
from apps.backend.core.database import Base  # noqa: F401
from apps.backend.models import models as _models  # noqa: F401  registers all models
from apps.backend.core.config import settings

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata — required for --autogenerate ─────────────────────────────
target_metadata = Base.metadata


# ── Migration runners ─────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """
    Run migrations using a URL string (no live DB connection needed).
    Only generates SQL scripts, does not execute them.
    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations within an async context.
    This is the correct pattern for SQLAlchemy asyncpg.
    """
    connectable = create_async_engine(settings.DATABASE_URL, echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection) -> None:
    """Synchronous migration runner (called inside run_sync)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Entry point for online migration mode (the default)."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
