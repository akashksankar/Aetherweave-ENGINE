"""
AetherWeave Backend — Celery Periodic Tasks (Beat tasks)
=========================================================

Implements the 3 Celery Beat scheduled tasks:
  1. health_ping          — alive signal every 60s
  2. cleanup_symbiosis_tokens — DB housekeeping every 6h
  3. auto_snapshot_idle_architectures — keeps idle graphs evolving

These tasks run inside the Celery worker process (not FastAPI).
They use `asyncio.run()` to drive async DB operations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from apps.backend.worker.celery_app import celery_app
from apps.backend.core.pubsub import publish_system_event

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@celery_app.task(name="tasks.health_ping", ignore_result=True)
def health_ping() -> None:
    """
    Heartbeat task — runs every 60 s.

    Publishes a system:events ping so the frontend StatusBar can confirm
    the Celery worker is alive. The FastAPI WebSocket subscriber forwards
    this event to all connected clients.
    """
    async def _ping() -> None:
        await publish_system_event({
            "type":      "worker_ping",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message":   "Celery worker alive",
        })

    try:
        asyncio.run(_ping())
    except Exception as e:
        logger.warning("health_ping_failed", error=str(e))


@celery_app.task(name="tasks.cleanup_symbiosis_tokens", ignore_result=True)
def cleanup_symbiosis_tokens() -> None:
    """
    Symbiosis token housekeeping — runs every 6 hours.

    Deletes SymbiosisToken rows where:
      - expires_at < NOW  (expired)
      - OR used == True   AND created_at < NOW - 7 days  (old used tokens)

    Uses raw SQLAlchemy core (not ORM) for efficiency on large token tables.
    """
    from sqlalchemy import text as sql_text

    async def _cleanup() -> int:
        from apps.backend.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            now = datetime.now(tz=timezone.utc)
            week_ago = now - timedelta(days=7)

            result = await db.execute(
                sql_text("""
                    DELETE FROM symbiosis_tokens
                    WHERE expires_at < :now
                       OR (used = TRUE AND created_at < :week_ago)
                """),
                {"now": now, "week_ago": week_ago},
            )
            await db.commit()
            return result.rowcount  # type: ignore[return-value]

    try:
        deleted = asyncio.run(_cleanup())
        logger.info("symbiosis_tokens_cleaned", deleted=deleted)
    except Exception as e:
        logger.error("symbiosis_cleanup_failed", error=str(e))


@celery_app.task(name="tasks.auto_snapshot_idle_architectures", ignore_result=True)
def auto_snapshot_idle_architectures() -> None:
    """
    Auto-evolution for idle architectures — runs every 5 minutes.

    Finds architectures that:
      - are NOT currently evolving (is_evolving == False)
      - have not been updated in the last 60 minutes
      - have a generation count < 100 (not yet mature)

    Runs a short 5-generation NSGA-II evolution on each (max 3 per run
    to avoid overloading the worker). Publishes a generation event to
    Redis for real-time WebSocket broadcasts.
    """
    async def _snapshot() -> None:
        from sqlalchemy import select, and_
        from apps.backend.core.database import AsyncSessionLocal
        from apps.backend.models.models import ArchGraphModel
        from apps.backend.services.enhanced_evolution_service import (
            enhanced_evolution_service,
        )
        from apps.backend.core.pubsub import publish_generation_event

        now = datetime.now(tz=timezone.utc)
        idle_cutoff = now - timedelta(minutes=60)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ArchGraphModel)
                .where(
                    and_(
                        ArchGraphModel.is_evolving == False,  # noqa: E712
                        ArchGraphModel.updated_at < idle_cutoff,
                        ArchGraphModel.generation < 100,
                    )
                )
                .limit(3)
            )
            idle_archs = list(result.scalars().all())

        if not idle_archs:
            return

        logger.info("auto_snapshot_found", count=len(idle_archs))

        for arch in idle_archs:
            arch_id = str(arch.id)
            intent  = arch.intent or "Autonomous evolution"
            try:
                async for event in enhanced_evolution_service.run_evolution(
                    intent=intent,
                    architecture_id=arch_id,
                    generations=5,
                    population_size=15,
                    enable_debate=False,  # Fast mode for auto-snapshot
                ):
                    await publish_generation_event(arch_id=arch_id, event=event)
                    if event.get("type") == "complete":
                        break
                logger.info("auto_snapshot_complete", arch_id=arch_id)
            except Exception as e:
                logger.error("auto_snapshot_failed", arch_id=arch_id, error=str(e))

    try:
        asyncio.run(_snapshot())
    except Exception as e:
        logger.error("auto_snapshot_task_failed", error=str(e))
