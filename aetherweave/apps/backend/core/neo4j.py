"""
AetherWeave Backend — Neo4j Graph Database Integration
======================================================

All architecture graphs are stored as nodes and relationships in Neo4j.
This module manages the driver lifecycle (init/close) and provides a
context-manager helper for acquiring sessions.

Neo4j schema:
  (:ArchNode {id, label, type, fitness, generation, ...})
  (:ArchGraph {id, name, generation, ...})
  (:ArchNode)-[:DEPENDS_ON {weight, label, latency_ms}]->(:ArchNode)
  (:ArchGraph)-[:CONTAINS]->(:ArchNode)

Init sequence:
  await init_neo4j()  → opens AsyncDriver + verifies connectivity
  await close_neo4j() → closes driver gracefully
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from apps.backend.core.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Module-level driver singleton ─────────────────────────────────────────────

_driver: AsyncDriver | None = None


async def init_neo4j() -> None:
    """
    Initialise the Neo4j async driver and verify connectivity.

    Uses the Bolt protocol for efficient binary serialisation.
    The driver maintains an internal connection pool so individual
    sessions are lightweight.

    Raises:
        neo4j.exceptions.ServiceUnavailable: If Neo4j is not reachable.
    """
    global _driver
    _driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
        max_connection_pool_size=50,
    )
    # Verify connectivity — raises if the DB is not reachable
    await _driver.verify_connectivity()
    logger.info("neo4j_initialised", uri=settings.NEO4J_URI)


async def close_neo4j() -> None:
    """Close the Neo4j driver and release all pooled connections."""
    global _driver
    if _driver is not None:
        await _driver.close()
        logger.info("neo4j_closed")
        _driver = None


def get_driver() -> AsyncDriver:
    """
    Return the module-level Neo4j driver.

    Raises:
        RuntimeError: If init_neo4j() has not been called.
    """
    if _driver is None:
        raise RuntimeError("Neo4j not initialised. Call init_neo4j() first.")
    return _driver


@asynccontextmanager
async def neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a Neo4j session.

    Usage:
        async with neo4j_session() as session:
            result = await session.run("MATCH (n) RETURN count(n)")

    Yields:
        An AsyncSession connected to the configured Neo4j database.
    """
    async with get_driver().session(database=settings.NEO4J_DATABASE) as session:
        yield session
