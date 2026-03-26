"""
AetherWeave Backend — WebSocket Connection Manager
====================================================

Manages all active WebSocket connections across multiple concurrent clients.
Allows the Redis pub/sub subscriber to broadcast generation events to every
connected client watching a specific architecture.

Architecture
------------
ConnectionManager maintains two registries:
  1. `_global`:  All connected sockets (for system-level broadcasts)
  2. `_by_arch`: Grouped by architecture ID (for targeted broadcasts)

Thread-safety: All mutation operations acquire an asyncio.Lock because
WebSocket connections are managed concurrently in the async event loop.

Usage (in FastAPI endpoints):
    # On connection:
    await manager.connect(websocket, arch_id="abc-123")
    # On disconnect:
    manager.disconnect(websocket)
    # To broadcast from Redis subscriber task:
    await manager.broadcast_to_arch(arch_id="abc-123", data=event_dict)

"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

import structlog
from fastapi import WebSocket

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Async WebSocket connection registry with targeted broadcast support.

    Attributes
    ----------
    _global   : list[WebSocket]
        All connected WebSocket clients (used for system broadcasts).
    _by_arch  : dict[str, list[WebSocket]]
        Connections grouped by architecture_id for per-arch broadcasts.
    _lock     : asyncio.Lock
        Async lock protecting all mutations to the registries.
    """

    def __init__(self) -> None:
        self._global:  list[WebSocket]                   = []
        self._by_arch: dict[str, list[WebSocket]]        = defaultdict(list)
        self._lock:    asyncio.Lock                      = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        arch_id:   str | None = None,
        accept:    bool = True,
    ) -> None:
        """
        Register an incoming WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance.
            arch_id:   Optional architecture ID to subscribe to targeted events.
            accept:    If True (default), calls websocket.accept() first.
        """
        if accept:
            await websocket.accept()
        async with self._lock:
            self._global.append(websocket)
            if arch_id:
                self._by_arch[arch_id].append(websocket)
        logger.info(
            "ws_connected",
            total_connections=len(self._global),
            arch_id=arch_id,
        )

    def disconnect(self, websocket: WebSocket, arch_id: str | None = None) -> None:
        """
        Remove a WebSocket from all registries (called on close or error).

        Args:
            websocket: The WebSocket to remove.
            arch_id:   The architecture ID it was subscribed to (optional).
        """
        try:
            self._global.remove(websocket)
        except ValueError:
            pass

        if arch_id and arch_id in self._by_arch:
            try:
                self._by_arch[arch_id].remove(websocket)
            except ValueError:
                pass
            # Clean up empty lists
            if not self._by_arch[arch_id]:
                del self._by_arch[arch_id]

        logger.info("ws_disconnected", total_connections=len(self._global))

    async def broadcast_to_arch(
        self,
        arch_id: str,
        data:    dict[str, Any],
    ) -> int:
        """
        Send a JSON payload to all clients subscribed to a specific architecture.

        Dead connections are silently removed during the broadcast.

        Args:
            arch_id: Architecture UUID string.
            data:    Dict to serialise as JSON and send to each client.

        Returns:
            Number of clients successfully reached.
        """
        if arch_id not in self._by_arch:
            return 0

        payload = json.dumps(data)
        dead:    list[WebSocket] = []
        count = 0

        for ws in list(self._by_arch.get(arch_id, [])):
            try:
                await ws.send_text(payload)
                count += 1
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, arch_id=arch_id)

        return count

    async def broadcast_global(self, data: dict[str, Any]) -> int:
        """
        Send a JSON payload to ALL connected clients.
        Used for system-level events (e.g. "a new architecture was created").

        Args:
            data: Dict to broadcast.

        Returns:
            Number of clients reached.
        """
        payload = json.dumps(data)
        dead:   list[WebSocket] = []
        count = 0

        for ws in list(self._global):
            try:
                await ws.send_text(payload)
                count += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

        return count

    @property
    def active_connections(self) -> int:
        """Total number of connected WebSocket clients."""
        return len(self._global)

    @property
    def subscribed_archs(self) -> list[str]:
        """List of architecture IDs with at least one subscriber."""
        return list(self._by_arch.keys())


# ── Module-level singleton ─────────────────────────────────────────────────────
# Shared across all FastAPI routes via Depends() or direct import.
manager = ConnectionManager()
