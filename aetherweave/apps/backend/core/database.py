"""
AetherWeave Backend — Async PostgreSQL Database Setup
=====================================================

Uses SQLAlchemy 2.0 async engine + session factory pattern.

Init sequence (called from main.py lifespan):
  await init_db()   → creates engine + creates tables if they don't exist
  await close_db()  → disposes engine (drains all pooled connections)

Usage in route handlers via dependency injection:
  async def my_endpoint(db: AsyncSession = Depends(get_db)):
      result = await db.execute(select(MyModel))
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from apps.backend.core.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── SQLAlchemy declarative base ───────────────────────────────────────────────


class Base(DeclarativeBase):
    """
    Root declarative base for all SQLAlchemy ORM models.

    All model classes must inherit from `Base` so that `metadata.create_all()`
    can discover them and create the corresponding tables.
    """

    pass


# ── Engine / session factory (module-level singletons) ───────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Initialize the SQLAlchemy async engine and create all tables.

    Creates a connection pool of `settings.DB_POOL_SIZE` connections to
    PostgreSQL and runs a connectivity check (SELECT 1) to fail fast if
    the database is unreachable.

    Raises:
        sqlalchemy.exc.OperationalError: If the database connection fails.
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,   # verify connections on checkout (avoids stale conn errors)
        pool_recycle=3600,    # recycle connections after 1 hour
    )

    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,  # attributes remain accessible after commit
        autoflush=False,
    )

    # Verify connectivity
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Create tables (idempotent; safe to call on every startup)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_initialised", pool_size=settings.DB_POOL_SIZE)


async def close_db() -> None:
    """
    Dispose the async engine, draining all pooled connections.
    Must be called during application shutdown to prevent connection leaks.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("database_closed")
        _engine = None


# ── Dependency ────────────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """
    FastAPI dependency that yields a database session for a single request.

    Automatically commits on success or rolls back on any exception,
    and always closes the session when the request is done.

    Usage:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...

    Yields:
        An AsyncSession bound to the current request lifecycle.

    Raises:
        RuntimeError: If the database has not been initialised.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
