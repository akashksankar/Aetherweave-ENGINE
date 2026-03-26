"""
AetherWeave Backend — FastAPI Application Entrypoint
=====================================================

This module bootstraps the entire FastAPI application:

1. Configures structured logging (structlog) for JSON log lines in production.
2. Manages application lifespan:
   - On startup: connects to PostgreSQL, Neo4j, Redis, and Celery.
   - On shutdown: gracefully closes all connections.
3. Mounts all API routers under /api/v1/.
4. Adds CORS middleware (permissive in dev, strict in prod).
5. Provides a basic health-check endpoint at GET /health.

Usage
-----
Development:
    uv run uvicorn apps.backend.main:app --reload --port 8000

Production:
    uv run uvicorn apps.backend.main:app --workers 4 --port 8000
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from apps.backend.core.config import settings
from apps.backend.core.database import close_db, init_db
from apps.backend.core.logging import configure_logging
from apps.backend.core.neo4j import close_neo4j, init_neo4j
from apps.backend.core.redis import close_redis, init_redis
from apps.backend.core.pubsub import start_redis_subscriber
from apps.backend.api.v1 import router as api_v1_router

# ── Logging setup ────────────────────────────────────────────────────────────

configure_logging(json_logs=not settings.DEBUG)
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Application start time (for uptime calculation) ──────────────────────────

_start_time: float = 0.0

# ── Lifespan context manager ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context — replaces deprecated @app.on_event decorators.

    Sequence on startup:
    1. Record start time.
    2. Initialise PostgreSQL connection pool (SQLAlchemy async engine).
    3. Initialise Neo4j driver.
    4. Initialise Redis connection pool.
    5. Log "ready" banner.

    Sequence on shutdown (runs after yield):
    1. Close Redis pool.
    2. Close Neo4j driver.
    3. Dispose SQLAlchemy engine (closes all PG connections gracefully).
    4. Log "shutdown" banner.

    Args:
        app: The FastAPI instance (injected by the framework).

    Yields:
        None — control returns to FastAPI to serve requests.
    """
    global _start_time
    _start_time = time.monotonic()

    logger.info(
        "aetherweave_starting",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )

    # 1. PostgreSQL
    await init_db()
    logger.info("postgres_connected")

    # 2. Neo4j
    await init_neo4j()
    logger.info("neo4j_connected")

    # 3. Redis
    await init_redis()
    logger.info("redis_connected")

    # 4. Start Redis pub/sub subscriber (long-lived background task)
    #    Forwards Redis channel messages → WebSocket clients via ConnectionManager
    _subscriber_task = asyncio.create_task(
        start_redis_subscriber(),
        name="redis-pubsub-subscriber",
    )
    logger.info("aetherweave_ready", host="0.0.0.0", port=8000)

    yield  # ← requests are served between startup and shutdown

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("aetherweave_shutting_down")
    _subscriber_task.cancel()
    try:
        await _subscriber_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    await close_neo4j()
    await close_db()
    logger.info("aetherweave_stopped")


# ── Application factory ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """
    Factory function that constructs and configures the FastAPI application.

    Separating construction from module-level instantiation enables clean
    testing (each test can call `create_app()` for an isolated instance).

    Returns:
        A fully configured FastAPI application instance.
    """
    app = FastAPI(
        title="AetherWeave API",
        description=(
            "Sentient 3D Living Architecture Loom — "
            "evolutionary AI-powered software architecture engine. "
            "Full OpenAPI docs available at /docs."
        ),
        version=settings.VERSION,
        lifespan=lifespan,
        # Only expose docs in non-production environments
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )

    # ── Middleware stack ──────────────────────────────────────────────────
    # GZip compression for large evolution-result payloads (> 500 bytes)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS — allow the Next.js dev server origin in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


# ── Module-level app instance ─────────────────────────────────────────────────

app: FastAPI = create_app()

# ── Endpoints registered directly on the root app ─────────────────────────────


@app.get(
    "/health",
    summary="Basic liveness probe",
    description=(
        "Returns HTTP 200 immediately if the process is alive. "
        "Used by Kubernetes liveness probes and load-balancer health checks. "
        "Does NOT verify database or cache connectivity — use /api/v1/status for that."
    ),
    response_description="{ 'status': 'ok' }",
    tags=["Infrastructure"],
)
async def health_check() -> JSONResponse:
    """
    Liveness check endpoint.

    Returns a minimal JSON payload as fast as possible.
    Intentionally has no database dependency so it never times out.

    Returns:
        JSONResponse with status 'ok' and process uptime in seconds.
    """
    uptime = round(float(time.monotonic() - _start_time), 2)
    return JSONResponse(
        content={"status": "ok", "uptime_seconds": uptime},
        status_code=200,
    )


# ── Dev entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "apps.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config=None,  # structlog handles all logging
    )
