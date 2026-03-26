"""
AetherWeave Backend — Redis Pub/Sub Broadcast Layer
====================================================

Provides a Redis-backed event bus for cross-process broadcasting.
When a Celery worker (running in a separate process/container) completes
an evolution generation, it publishes the event to a Redis channel.
The FastAPI process subscribes to that channel and broadcasts it to
all connected WebSocket clients via the ConnectionManager.

Channel naming convention:
  arch:{architecture_id}:events  → per-architecture generation events
  system:events                  → global events (arch created, etc.)

Architecture diagram:

  [Celery Worker]
      │  publish("arch:abc:events", json)
      ▼
  [Redis Pub/Sub]
      │  subscribe + async receive
      ▼
  [FastAPI lifespan task: _redis_subscriber()]
      │  manager.broadcast_to_arch(arch_id, event)
      ▼
  [All connected WebSocket clients watching arch:abc]

The subscriber task starts in main.py's lifespan (async context manager)
so it runs for the entire application lifetime and shuts down cleanly.

Usage in services or Celery tasks:
    from apps.backend.core.pubsub import publish_generation_event
    await publish_generation_event(arch_id="abc-123", event=payload)

Usage in main.py lifespan:
    asyncio.create_task(start_redis_subscriber())
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from apps.backend.core.redis  import get_redis_client
from apps.backend.core.ws_manager import manager

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Channel helpers ────────────────────────────────────────────────────────────

def arch_channel(arch_id: str) -> str:
    """Return the Redis pub/sub channel name for an architecture."""
    return f"arch:{arch_id}:events"

SYSTEM_CHANNEL = "system:events"


# ── Publisher (called from Celery workers or services) ─────────────────────────

async def publish_generation_event(
    arch_id: str,
    event:   dict[str, Any],
) -> None:
    """
    Publish a generation event to the Redis pub/sub channel.

    Called by the enhanced EvolutionService or Celery task after each
    DEAP generation completes. FastAPI's subscriber task picks this up
    and forwards it to all WebSocket clients watching this architecture.

    Args:
        arch_id: Architecture UUID string.
        event:   WSGenerationEvent dict to publish.
    """
    async with get_redis_client() as redis:
        channel = arch_channel(arch_id)
        payload = json.dumps(event)
        await redis.publish(channel, payload)
        logger.debug("redis_published", channel=channel, event_type=event.get("type"))


async def publish_system_event(event: dict[str, Any]) -> None:
    """
    Publish a global system event (e.g. new architecture created).

    Broadcast to all connected WebSocket clients regardless of which
    architecture they are watching.

    Args:
        event: System event dict.
    """
    async with get_redis_client() as redis:
        payload = json.dumps(event)
        await redis.publish(SYSTEM_CHANNEL, payload)
        logger.debug("redis_system_published", event_type=event.get("type"))


# ── Subscriber (runs as a long-lived asyncio task in FastAPI lifespan) ─────────

async def start_redis_subscriber() -> None:
    """
    Long-running asyncio task that subscribes to all Redis pub/sub channels.

    Starts in main.py's lifespan. Loops forever receiving messages and
    dispatching them to the ConnectionManager's broadcaster.

    Channels subscribed:
      - "system:events"          → broadcast_global()
      - "arch:*:events" (psubscribe pattern) → broadcast_to_arch()

    Error handling:
      - On Redis disconnection: sleeps 2s then reconnects.
      - Never raises (silently restarts) to avoid crashing the app.
    """
    logger.info("redis_subscriber_starting")

    while True:
        try:
            async with get_redis_client() as redis:
                pubsub = redis.pubsub()

                # Subscribe to system events + pattern for all arch events
                await pubsub.subscribe(SYSTEM_CHANNEL)
                await pubsub.psubscribe("arch:*:events")

                logger.info("redis_subscriber_connected")

                async for message in pubsub.listen():
                    if message["type"] not in ("message", "pmessage"):
                        continue

                    try:
                        data = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    channel = message.get("channel", b"").decode(
                        "utf-8", errors="ignore"
                    )

                    if channel == SYSTEM_CHANNEL:
                        # Broadcast to all connected clients
                        await manager.broadcast_global(data)

                    elif channel.startswith("arch:") and channel.endswith(":events"):
                        # Extract architecture ID and targeted broadcast
                        parts = channel.split(":")
                        if len(parts) == 3:
                            arch_id   = parts[1]
                            n_clients = await manager.broadcast_to_arch(arch_id, data)
                            logger.debug(
                                "redis_broadcast",
                                arch_id=arch_id,
                                clients=n_clients,
                                event_type=data.get("type"),
                            )

        except asyncio.CancelledError:
            logger.info("redis_subscriber_cancelled")
            break
        except Exception as e:
            logger.error("redis_subscriber_error", error=str(e))
            await asyncio.sleep(2)  # Back-off before reconnecting
