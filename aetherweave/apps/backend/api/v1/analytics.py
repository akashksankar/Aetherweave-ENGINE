"""
AetherWeave Backend — Analytics + Pareto Front API
===================================================

REST endpoints for Neo4j graph analytics and NSGA-II Pareto front data.

GET /api/v1/analytics/{graph_id}
    Runs the 4-query Neo4j analytics pipeline and returns the result.
    Results are cached in Redis for 60s to avoid re-running on every poll.

GET /api/v1/analytics/{graph_id}/pareto
    Returns the last known Pareto front individuals stored in the
    evolution_runs table for this architecture.

POST /api/v1/architecture/{graph_id}/symbiosis/redeem
    Validates and redeems a symbiosis token. If password-protected,
    requires the password. Returns the shared architecture JSON for
    the frontend to merge into the active graph.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.database import get_db
from apps.backend.core.redis import get_redis_client
from apps.backend.services.analytics_service import analytics_service
from apps.backend.models.models import EvolutionRunModel, SymbiosisTokenModel, ArchGraphModel

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

ANALYTICS_TTL = 60  # Redis cache TTL in seconds


# ── Graph analytics ───────────────────────────────────────────────────────────

@router.get(
    "/{graph_id}",
    summary="Run Neo4j graph analytics",
    description=(
        "Executes 4 concurrent Cypher queries on Neo4j: "
        "bottleneck detection, cluster analysis, critical path, and hub detection. "
        "Results are cached in Redis for 60 seconds."
    ),
)
async def get_analytics(graph_id: str) -> JSONResponse:
    """
    Fetch or compute analytics for a graph.

    First checks Redis for a cached result (TTL 60s).
    On cache miss, runs all 4 Neo4j queries concurrently and stores the result.

    Args:
        graph_id: UUID of the architecture graph.

    Returns:
        AnalyticsResult as JSON.
    """
    cache_key = f"analytics:{graph_id}"

    # ── Cache lookup ───────────────────────────────────────────────────────
    try:
        async with get_redis_client() as redis:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("analytics_cache_hit", graph_id=graph_id)
                return JSONResponse(content=json.loads(cached))
    except Exception:
        pass  # Redis unavailable — fall through to fresh query

    # ── Fresh analytics ────────────────────────────────────────────────────
    try:
        result = await analytics_service.analyse(graph_id)
        payload = result.model_dump()

        # Store in Redis
        try:
            async with get_redis_client() as redis:
                await redis.setex(cache_key, ANALYTICS_TTL, json.dumps(payload))
        except Exception:
            pass

        return JSONResponse(content=payload)

    except Exception as e:
        logger.error("analytics_failed", graph_id=graph_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Analytics query failed: {str(e)}",
        )


# ── Pareto front ──────────────────────────────────────────────────────────────

@router.get(
    "/{graph_id}/pareto",
    summary="Get NSGA-II Pareto front",
    description=(
        "Returns the Pareto-optimal individuals from the last completed "
        "evolution run for this architecture."
    ),
)
async def get_pareto_front(
    graph_id: str,
    db:       AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Fetch Pareto front data from the latest evolution run.

    Reads the `pareto_front` JSON column from the EvolutionRunModel.
    If no completed run exists, returns an empty front.

    Args:
        graph_id: UUID of the architecture graph.
        db:       Database session.

    Returns:
        ParetoFrontResult-shaped JSON.
    """
    import uuid
    try:
        uid = uuid.UUID(graph_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid graph_id format.")

    result = await db.execute(
        select(EvolutionRunModel)
        .where(
            EvolutionRunModel.graph_id == uid,
            EvolutionRunModel.status   == "complete",
        )
        .order_by(EvolutionRunModel.finished_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()

    if not run or not run.pareto_front:
        return JSONResponse(content={
            "graph_id":    graph_id,
            "individuals": [],
            "front_size":  0,
            "dominated":   0,
        })

    individuals = run.pareto_front if isinstance(run.pareto_front, list) else []
    return JSONResponse(content={
        "graph_id":    graph_id,
        "individuals": individuals,
        "front_size":  len(individuals),
        "dominated":   run.generations_run * 15 - len(individuals),
    })


# ── Symbiosis redeem ──────────────────────────────────────────────────────────

@router.post(
    "/symbiosis/redeem",
    summary="Redeem a symbiosis DNA token",
    description=(
        "Validates the symbiosis token, marks it as used, and returns "
        "the shared architecture DNA for merging into the recipient's active graph."
    ),
)
async def redeem_symbiosis_token(
    token:    str,
    password: str | None = None,
    db:       AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Redeem a symbiosis token and return the shared architecture.

    Args:
        token:    The unique token string from the QR code URL.
        password: Optional password if the token was created with one.
        db:       Database session.

    Returns:
        { architecture: ArchGraph, merged_nodes: int, donor_fitness: float }
    """
    from apps.backend.models.models import SymbiosisTokenModel

    result = await db.execute(
        select(SymbiosisTokenModel).where(SymbiosisTokenModel.token == token)
    )
    sym_token = result.scalar_one_or_none()

    if not sym_token:
        raise HTTPException(status_code=404, detail="Token not found.")
    if sym_token.used:
        raise HTTPException(status_code=410, detail="Token already redeemed.")

    now = datetime.now(tz=timezone.utc)
    # Handle both timezone-aware and naive expirations
    expires = sym_token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if expires < now:
        raise HTTPException(status_code=410, detail="Token has expired.")

    # Password check
    if sym_token.password_hash:
        if not password:
            raise HTTPException(status_code=401, detail="This token is password-protected.")
        import bcrypt
        if not bcrypt.checkpw(
            password.encode(),
            sym_token.password_hash.encode(),
        ):
            raise HTTPException(status_code=403, detail="Incorrect password.")

    # Fetch the shared architecture
    arch_result = await db.execute(
        select(ArchGraphModel).where(ArchGraphModel.id == sym_token.graph_id)
    )
    arch = arch_result.scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Shared architecture no longer exists.")

    # Mark token as used
    sym_token.used = True
    sym_token.redeemed_at = now
    await db.commit()

    logger.info(
        "symbiosis_token_redeemed",
        token=str(token)[:8],
        graph_id=str(sym_token.graph_id),
    )

    return JSONResponse(content={
        "architecture":   {
            "id":     str(arch.id),
            "name":   arch.name,
            "nodes":  arch.nodes,
            "edges":  arch.edges,
            "intent": arch.intent,
        },
        "merged_nodes": len(arch.nodes),
        "donor_fitness": arch.fitness_aggregate,
        "message": f"Symbiosis complete — {len(arch.nodes)} nodes imported from '{arch.name}'.",
    })
