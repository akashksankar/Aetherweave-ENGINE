"""
AetherWeave Backend — /api/v1/status Endpoint
=============================================

Returns the full system health status including all backing services.
This endpoint is used by:
- The frontend dashboard to show connection indicators.
- Kubernetes readiness probes (HTTP 503 if any service is down).
- External monitoring / uptime checks.

Response shape mirrors SystemStatus in packages/shared/types.py.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from apps.backend.core.config import settings
from apps.backend.core.neo4j import get_driver
from apps.backend.core.redis import get_redis

# Start time is imported from main to calculate uptime
_process_start: float = time.monotonic()

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


async def _check_postgres() -> str:
    """Ping PostgreSQL by running a trivial query. Returns 'up' or 'down'."""
    try:
        from apps.backend.core.database import get_db
        # A quick way to verify without a route dependency injection
        from sqlalchemy import text
        from apps.backend.core.database import _engine
        if _engine is None:
            return "down"
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "up"
    except Exception as e:
        logger.warning("postgres_health_check_failed", error=str(e))
        return "down"


async def _check_neo4j() -> str:
    """Verify the Neo4j driver can reach the database. Returns 'up' or 'down'."""
    try:
        driver = get_driver()
        await driver.verify_connectivity()
        return "up"
    except Exception as e:
        logger.warning("neo4j_health_check_failed", error=str(e))
        return "down"


async def _check_redis() -> str:
    """Ping Redis. Returns 'up' or 'down'."""
    try:
        r = get_redis()
        await r.ping()
        return "up"
    except Exception as e:
        logger.warning("redis_health_check_failed", error=str(e))
        return "down"


async def _check_celery() -> str:
    """
    Check if any Celery workers are available by inspecting active workers.
    Returns 'up' if at least one worker responds, 'down' otherwise.
    """
    try:
        from apps.backend.worker.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1)
        active = inspector.active()
        return "up" if active else "down"
    except Exception as e:
        logger.warning("celery_health_check_failed", error=str(e))
        return "down"


@router.get(
    "/status",
    summary="Full system health status",
    description=(
        "Returns the operational status of all AetherWeave backend services: "
        "PostgreSQL, Neo4j, Redis, and Celery. "
        "Returns HTTP 200 when all services are healthy, "
        "503 when at least one is degraded or down. "
        "The frontend uses this to render connection status indicators."
    ),
    response_description="SystemStatus object with per-service health flags",
    tags=["System"],
)
async def get_status() -> JSONResponse:
    """
    Full readiness check — verifies all backing services.

    Unlike /health (which only checks process liveness), this endpoint
    actively queries each service and returns their status.

    Returns:
        JSONResponse with SystemStatus payload.
        HTTP 200 if all services are 'up'.
        HTTP 503 if any service is 'down' or 'degraded'.
    """
    # Run all service checks concurrently for minimum latency
    import asyncio
    postgres, neo4j, redis, celery_status = await asyncio.gather(
        _check_postgres(),
        _check_neo4j(),
        _check_redis(),
        _check_celery(),
    )

    services = {
        "postgres": postgres,
        "neo4j": neo4j,
        "redis": redis,
        "celery": celery_status,
    }

    # Determine overall health
    all_up = all(v == "up" for v in services.values())
    any_down = any(v == "down" for v in services.values())

    if all_up:
        overall = "healthy"
        http_status = 200
    elif any_down:
        overall = "unhealthy"
        http_status = 503
    else:
        overall = "degraded"
        http_status = 503

    uptime = round(time.monotonic() - _process_start, 2)

    payload = {
        "status": overall,
        "version": settings.VERSION,
        "uptime": uptime,
        "services": services,
        "active_evolutions": 0,   # populated in Part 2 by EvolutionService
        "total_architectures": 0, # populated in Part 2 by ArchitectureService
    }

    logger.info("status_check", **payload)
    return JSONResponse(content=payload, status_code=http_status)
