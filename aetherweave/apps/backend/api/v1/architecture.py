"""
AetherWeave Backend — Enhanced Architecture Search + Filter API
================================================================

Adds search, filter, and sort capabilities to the architecture list endpoint:

  GET /api/v1/architecture
    ?q=<intent_search>
    &min_fitness=<float>
    &max_fitness=<float>
    &sort=<fitness|generation|created_at>
    &order=<asc|desc>
    &limit=<int>
    &offset=<int>

Also adds:
  GET /api/v1/architecture/{id}/mutations
    Returns the mutation audit trail for an architecture.

  GET /api/v1/architecture/{id}/evolution-runs
    Returns completed evolution run summaries.

  POST /api/v1/architecture/{id}/notify
    Sends a system event to all WebSocket clients watching this architecture.
    Used to announce graph-level mutations from external processes.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.database import get_db
from apps.backend.core.ws_manager import manager
from apps.backend.core.pubsub import publish_system_event
from apps.backend.models.models import (
    ArchGraphModel,
    MutationModel,
    EvolutionRunModel,
)
from apps.backend.services.architecture_service import ArchitectureService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/architecture", tags=["Architecture"])
_arch_service = ArchitectureService()


# ── Enhanced list with search + filter ────────────────────────────────────────


@router.get(
    "",
    summary="Search and filter architectures",
    description=(
        "Paginated list with optional full-text intent search, fitness range filter, "
        "and flexible sort. Uses PostgreSQL ILIKE for case-insensitive search."
    ),
)
async def list_architectures(
    q:           str   | None = Query(None,  description="Search term matched against intent (case-insensitive)"),
    min_fitness: float | None = Query(None,  ge=0.0, le=1.0, description="Minimum aggregate fitness"),
    max_fitness: float | None = Query(None,  ge=0.0, le=1.0, description="Maximum aggregate fitness"),
    sort:        str          = Query("created_at", pattern="^(fitness|generation|created_at)$"),
    order:       str          = Query("desc",       pattern="^(asc|desc)$"),
    limit:       int          = Query(20, ge=1, le=100),
    offset:      int          = Query(0,  ge=0),
    db:          AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    List architectures with full search, filter, and sort.

    Args:
        q:           Optional intent search string (ILIKE).
        min_fitness: Filter by minimum aggregate fitness score.
        max_fitness: Filter by maximum aggregate fitness score.
        sort:        Column to sort by (fitness|generation|created_at).
        order:       Sort direction (asc|desc).
        limit:       Page size.
        offset:      Page offset.
        db:          Database session.

    Returns:
        { total, items, filters_applied } JSON response.
    """
    stmt = select(ArchGraphModel)

    # ── Filters ────────────────────────────────────────────────────────────
    filters = []
    if q:
        filters.append(ArchGraphModel.intent.ilike(f"%{q}%"))
    if min_fitness is not None:
        filters.append(ArchGraphModel.fitness_aggregate >= min_fitness)
    if max_fitness is not None:
        filters.append(ArchGraphModel.fitness_aggregate <= max_fitness)

    if filters:
        stmt = stmt.where(and_(*filters))

    # ── Sort ───────────────────────────────────────────────────────────────
    sort_col = {
        "fitness":    ArchGraphModel.fitness_aggregate,
        "generation": ArchGraphModel.generation,
        "created_at": ArchGraphModel.created_at,
    }[sort]

    stmt = stmt.order_by(
        sort_col.desc() if order == "desc" else sort_col.asc()
    )

    # ── Count total (for pagination) ───────────────────────────────────────
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # ── Page ───────────────────────────────────────────────────────────────
    result = await db.execute(stmt.limit(limit).offset(offset))
    graphs = list(result.scalars().all())

    items = [
        {
            "id":         str(g.id),
            "name":       g.name,
            "intent":     g.intent[:120] + "…" if len(g.intent) > 120 else g.intent,
            "generation": g.generation,
            "fitness":    {"aggregate": g.fitness_aggregate},
            "nodeCount":  len(g.nodes),
            "isEvolving": g.is_evolving,
            "createdAt":  g.created_at.isoformat(),
        }
        for g in graphs
    ]

    return JSONResponse(content={
        "total":   total,
        "items":   items,
        "filters": {
            "q":          q,
            "min_fitness": min_fitness,
            "max_fitness": max_fitness,
            "sort":        sort,
            "order":       order,
        },
    })


# ── Mutation audit trail ───────────────────────────────────────────────────────


@router.get(
    "/{graph_id}/mutations",
    summary="Get mutation audit trail",
    description="Returns the last 100 mutations applied to this architecture's evolution history.",
)
async def get_mutations(
    graph_id: str,
    limit:    int = Query(50, ge=1, le=100),
    db:       AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Fetch mutation audit trail for an architecture."""
    from apps.backend.models.models import MutationModel
    import uuid

    try:
        uid = uuid.UUID(graph_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid graph_id format.")

    result = await db.execute(
        select(MutationModel)
        .where(MutationModel.graph_id == uid)
        .order_by(MutationModel.timestamp.desc())
        .limit(limit)
    )
    mutations = list(result.scalars().all())

    return JSONResponse(content={
        "graph_id":  graph_id,
        "mutations": [
            {
                "id":           str(m.id),
                "generation":   m.generation,
                "type":         m.mutation_type,
                "nodeId":       str(m.node_id),
                "fitnessDelta": m.fitness_delta,
                "rationale":    m.rationale,
                "timestamp":    m.timestamp.isoformat(),
            }
            for m in mutations
        ],
    })


# ── Evolution run summaries ────────────────────────────────────────────────────


@router.get(
    "/{graph_id}/evolution-runs",
    summary="Get evolution run history",
    description="Returns all completed and queued evolution runs for this architecture.",
)
async def get_evolution_runs(
    graph_id: str,
    db:       AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Fetch evolution run history for an architecture."""
    import uuid

    try:
        uid = uuid.UUID(graph_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid graph_id format.")

    result = await db.execute(
        select(EvolutionRunModel)
        .where(EvolutionRunModel.graph_id == uid)
        .order_by(EvolutionRunModel.started_at.desc())
        .limit(20)
    )
    runs = list(result.scalars().all())

    return JSONResponse(content={
        "graph_id": graph_id,
        "runs": [
            {
                "id":                  str(r.id),
                "status":              r.status,
                "generationsRequested": r.generations_requested,
                "generationsRun":      r.generations_run,
                "finalFitness":        r.final_fitness,
                "durationMs":          r.duration_ms,
                "startedAt":           r.started_at.isoformat(),
                "finishedAt":          r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ],
    })


# ── WebSocket notification push ────────────────────────────────────────────────


class NotifyRequest(BaseModel):
    """Request body for POST /notify."""
    event_type: str = Field(..., description="Event type identifier")
    payload:    dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/{graph_id}/notify",
    status_code=status.HTTP_200_OK,
    summary="Push a WebSocket notification to architecture watchers",
    description=(
        "Sends a custom event to all WebSocket clients subscribed to this architecture. "
        "Also publishes to the Redis channel for cross-process broadcast."
    ),
)
async def notify_architecture_watchers(
    graph_id: str,
    body:     NotifyRequest,
    db:       AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Push a notification to all clients watching an architecture."""
    # Verify the architecture exists
    arch = await _arch_service.get(db, graph_id)
    if arch is None:
        raise HTTPException(status_code=404, detail="Architecture not found.")

    event = {
        "type":      body.event_type,
        "graphId":   graph_id,
        **body.payload,
    }

    # Direct broadcast to connected sockets
    local_clients = await manager.broadcast_to_arch(graph_id, event)

    # Also publish to Redis for cross-process/cross-instance broadcast
    from apps.backend.core.pubsub import publish_generation_event
    await publish_generation_event(arch_id=graph_id, event=event)

    return JSONResponse(content={
        "sent_to": local_clients,
        "event_type": body.event_type,
    })
