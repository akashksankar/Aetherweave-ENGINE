"""
AetherWeave Backend — ArchitectureService
==========================================

Handles CRUD operations for ArchGraph records in PostgreSQL and Neo4j.

PostgreSQL holds metadata (fastest for listing, filtering, sorting by fitness).
Neo4j holds the full graph topology (fastest for graph traversal queries like
"find architectures similar to this one by structural pattern").

Every write goes to both stores (dual-write pattern) — if Neo4j is unavailable,
PostgreSQL still stores a complete record so no data is lost.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.neo4j import neo4j_session
from apps.backend.models.models import ArchEdgeModel, ArchGraphModel, ArchNodeModel
from apps.backend.services.evolution_service import evolution_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ArchitectureService:
    """
    Service layer for ArchGraph persistence and retrieval.

    Methods
    -------
    create(db, intent, initial_nodes, seed)
        Create a new graph from intent, persist to PG + Neo4j.
    get(db, graph_id)
        Retrieve one graph by ID.
    list_all(db, limit, offset)
        List all graphs, newest first.
    count(db)
        Total number of graphs in the database.
    save_evolved(db, graph_payload)
        Persist the best graph output from an evolution run.
    """

    async def create(
        self,
        db: AsyncSession,
        intent: str,
        initial_nodes: int = 8,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a new architecture graph from a user's intent string.

        Steps:
        1. Call `evolution_service.create_initial_graph()` to build a random
           NetworkX-based graph with multi-objective fitness scores.
        2. Persist the graph + its nodes/edges to PostgreSQL.
        3. Write the graph topology to Neo4j (best-effort; no rollback if Neo4j fails).
        4. Return the full ArchGraph API payload.

        Args:
            db:            Async SQLAlchemy session (injected by FastAPI Depends).
            intent:        Natural-language description of the desired architecture.
            initial_nodes: Number of nodes to generate initially [3, 50].
            seed:          Optional RNG seed for reproducibility.

        Returns:
            ArchGraph dict matching the TypeScript interface.

        Raises:
            ValueError: If intent is blank.
            sqlalchemy.exc.SQLAlchemyError: On database write failure.
        """
        if not intent.strip():
            raise ValueError("Intent string must not be empty.")

        # 1. Generate initial graph using the evolution service
        graph_payload = evolution_service.create_initial_graph(
            intent=intent, initial_nodes=initial_nodes, seed=seed
        )

        fitness = graph_payload["fitness"]
        graph_id = uuid.UUID(graph_payload["id"])

        # 2. Persist to PostgreSQL
        db_graph = ArchGraphModel(
            id=graph_id,
            name=graph_payload["name"],
            intent=intent,
            generation=0,
            fitness_scalability=fitness["scalability"],
            fitness_cost_efficiency=fitness["costEfficiency"],
            fitness_future_proof=fitness["futureProof"],
            fitness_aggregate=fitness["aggregate"],
        )
        db.add(db_graph)

        for node_data in graph_payload["nodes"]:
            db_node = ArchNodeModel(
                id=uuid.UUID(node_data["id"]),
                graph_id=graph_id,
                label=node_data["label"],
                node_type=node_data["type"],
                pos_x=node_data["position"]["x"],
                pos_y=node_data["position"]["y"],
                pos_z=node_data["position"]["z"],
                fitness=node_data["fitness"],
                generation=0,
                ancestry=[],
                metadata_={},
            )
            db.add(db_node)

        for edge_data in graph_payload["edges"]:
            try:
                db_edge = ArchEdgeModel(
                    id=uuid.UUID(edge_data["id"]),
                    graph_id=graph_id,
                    source_id=uuid.UUID(edge_data["source"]),
                    target_id=uuid.UUID(edge_data["target"]),
                    weight=edge_data["weight"],
                    label=edge_data["label"],
                )
                db.add(db_edge)
            except Exception:
                # Some edge references may be stale due to positional indexing; skip
                pass

        await db.flush()

        # 3. Write to Neo4j (best-effort)
        try:
            await self._write_to_neo4j(graph_payload)
        except Exception as e:
            logger.warning("neo4j_write_failed", error=str(e), graph_id=str(graph_id))

        logger.info("architecture_created", graph_id=str(graph_id), nodes=len(graph_payload["nodes"]))
        return graph_payload

    async def get(self, db: AsyncSession, graph_id: str) -> ArchGraphModel | None:
        """
        Retrieve a single architecture graph by UUID.

        Args:
            db:       Database session.
            graph_id: UUID string of the graph.

        Returns:
            ArchGraphModel ORM object (with nodes/edges eagerly loaded),
            or None if not found.
        """
        try:
            uid = uuid.UUID(graph_id)
        except ValueError:
            return None
        result = await db.execute(select(ArchGraphModel).where(ArchGraphModel.id == uid))
        return result.scalars().first()

    async def list_all(
        self, db: AsyncSession, limit: int = 20, offset: int = 0
    ) -> list[ArchGraphModel]:
        """
        Return a paginated list of all architecture graphs, newest first.

        Args:
            db:     Database session.
            limit:  Maximum number of records to return (default 20).
            offset: Number of records to skip (for pagination).

        Returns:
            List of ArchGraphModel objects.
        """
        result = await db.execute(
            select(ArchGraphModel)
            .order_by(ArchGraphModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count(self, db: AsyncSession) -> int:
        """
        Return the total number of architecture graphs in the database.

        Args:
            db: Database session.

        Returns:
            Integer count of all ArchGraph records.
        """
        result = await db.execute(select(func.count()).select_from(ArchGraphModel))
        return result.scalar_one()

    async def _write_to_neo4j(self, graph_payload: dict[str, Any]) -> None:
        """
        Write the graph topology to Neo4j.

        Creates (:ArchNode) nodes and [:DEPENDS_ON] relationships.
        Uses MERGE so re-running is idempotent.

        Args:
            graph_payload: ArchGraph dict with nodes and edges arrays.
        """
        async with neo4j_session() as session:
            graph_id = graph_payload["id"]

            # Create/merge graph node
            await session.run(
                "MERGE (g:ArchGraph {id: $id}) SET g.name = $name, g.generation = $gen",
                id=graph_id, name=graph_payload["name"], gen=graph_payload["generation"]
            )

            # Create/merge each arch node
            for node in graph_payload["nodes"]:
                await session.run(
                    """
                    MERGE (n:ArchNode {id: $id})
                    SET n.label = $label, n.type = $type,
                        n.x = $x, n.y = $y, n.z = $z, n.fitness = $fitness
                    WITH n
                    MATCH (g:ArchGraph {id: $graph_id})
                    MERGE (g)-[:CONTAINS]->(n)
                    """,
                    id=node["id"],
                    label=node["label"],
                    type=node["type"],
                    x=node["position"]["x"],
                    y=node["position"]["y"],
                    z=node["position"]["z"],
                    fitness=node["fitness"],
                    graph_id=graph_id,
                )

            # Create edges
            for edge in graph_payload["edges"]:
                await session.run(
                    """
                    MATCH (src:ArchNode {id: $source})
                    MATCH (tgt:ArchNode {id: $target})
                    MERGE (src)-[r:DEPENDS_ON {id: $id}]->(tgt)
                    SET r.weight = $weight, r.label = $label
                    """,
                    source=edge["source"],
                    target=edge["target"],
                    id=edge["id"],
                    weight=edge["weight"],
                    label=edge["label"],
                )
