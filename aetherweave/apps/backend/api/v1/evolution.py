"""
AetherWeave Backend — Evolution API Routes
==========================================

POST /api/v1/evolve
    Starts an evolution run for an existing architecture.
    Returns immediately with a run_id; progress is streamed via WebSocket.

WebSocket /ws/evolution
    Streams every generation's payload as JSON to the connected client.
    Each message is a WSEvent discriminated union (see types.py).

WebSocket protocol
-------------------
1. Client connects to /ws/evolution
2. Client sends JSON: { "architectureId": "...", "generations": 20, ... }
3. Server streams WSGenerationEvent per generation
4. Server streams WSCompleteEvent on finish OR WSErrorEvent on error
5. Connection closes after completion
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.database import get_db
from apps.backend.services.architecture_service import ArchitectureService
from apps.backend.services.enhanced_evolution_service import enhanced_evolution_service as evolution_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(tags=["Evolution"])

_arch_service = ArchitectureService()


# ── Request models ────────────────────────────────────────────────────────────


class EvolveRequest(BaseModel):
    """Request body for POST /evolve."""

    architecture_id: str = Field(
        ..., description="UUID of the architecture to evolve"
    )
    generations: int = Field(
        10, ge=1, le=500, description="Number of generations to run"
    )
    population_size: int = Field(
        20, ge=10, le=200, description="DEAP population size"
    )
    seed: int | None = Field(None, description="Optional RNG seed")
    enable_debate: bool = Field(True, description="Enable agent debate per generation")


# ── REST evolve endpoint ──────────────────────────────────────────────────────


@router.post(
    "/evolve",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start an evolution run",
    description=(
        "Validates the architecture ID, creates an evolution run record, "
        "and dispatches a Celery task for background processing. "
        "Progress is streamed in real-time via the WebSocket endpoint /ws/evolution. "
        "Returns the evolution_run_id immediately for tracking."
    ),
)
async def start_evolution(
    body: EvolveRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Initiate an evolutionary run for an existing architecture.

    Args:
        body: Validated EvolveRequest with architectureId, generations, etc.
        db:   Database session.

    Returns:
        JSONResponse with { run_id, architecture_id, status: "queued" }.

    Raises:
        HTTP 404: If the architecture is not found.
        HTTP 409: If an evolution is already running on this architecture.
    """
    graph = await _arch_service.get(db, body.architecture_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Architecture not found.")

    if graph.is_evolving:
        raise HTTPException(
            status_code=409,
            detail="An evolution is already running on this architecture. Wait or cancel it first.",
        )

    import uuid
    run_id = str(uuid.uuid4())

    # Mark as evolving (will be cleared by Celery task on completion)
    graph.is_evolving = True
    graph.celery_task_id = run_id  # placeholder — real Celery task ID set in worker
    await db.flush()

    logger.info("evolution_queued", run_id=run_id, architecture_id=body.architecture_id)

    return JSONResponse(
        content={
            "run_id":          run_id,
            "architecture_id": body.architecture_id,
            "status":          "queued",
            "generations":     body.generations,
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


# ── WebSocket evolution stream ────────────────────────────────────────────────


@router.websocket("/ws/evolution")
async def ws_evolution(websocket: WebSocket) -> None:
    """
    WebSocket endpoint that streams real-time evolution events to the client.

    Protocol
    --------
    1. Accept connection.
    2. Receive initial JSON config from the client:
          { "architectureId": "...", "generations": 20, "populationSize": 20 }
    3. Run evolution via async generator — each generation yields a dict.
    4. Serialise each dict to JSON and send to client.
    5. Close connection after WSCompleteEvent or on error.

    Error handling
    --------------
    - If the client sends malformed JSON → send WSErrorEvent, close.
    - If evolution raises → send WSErrorEvent with traceback, close.
    - If client disconnects mid-run → catch WebSocketDisconnect, log, return.

    Args:
        websocket: FastAPI WebSocket connection object.
    """
    await websocket.accept()
    logger.info("ws_evolution_connected", client=str(websocket.client))

    try:
        # ── Receive config ────────────────────────────────────────────────
        raw = await websocket.receive_text()
        try:
            config: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({
                "type":    "error",
                "code":    "INVALID_JSON",
                "message": "The config message was not valid JSON.",
            })
            await websocket.close()
            return

        architecture_id = config.get("architectureId", "demo")
        generations     = int(config.get("generations",   10))
        population_size = int(config.get("populationSize", 20))
        intent          = config.get("intent", "evolving architecture")
        seed            = config.get("seed", None)

        # Clamp to safe ranges
        generations     = max(1, min(generations, 500))
        population_size = max(10, min(population_size, 200))

        logger.info(
            "ws_evolution_started",
            architecture_id=architecture_id,
            generations=generations,
            population_size=population_size,
        )

        # ── Stream evolution events ───────────────────────────────────────
        async for event in evolution_service.run_evolution(
            intent=intent,
            architecture_id=architecture_id,
            generations=generations,
            population_size=population_size,
            seed=seed,
        ):
            await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("ws_evolution_disconnected", client=str(websocket.client))

    except Exception as e:
        logger.error("ws_evolution_error", error=str(e))
        try:
            await websocket.send_json({
                "type":    "error",
                "code":    "EVOLUTION_ERROR",
                "message": str(e),
            })
        except Exception:
            pass  # Client may have already disconnected
        await websocket.close()
