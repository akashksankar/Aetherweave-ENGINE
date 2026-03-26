"""
AetherWeave Backend — Neo4j Graph Analytics Service
=====================================================

Provides deep graph-theoretic analytics using Cypher queries on Neo4j.

Analyses performed on every completed graph:
  1. Bottleneck Detection
     Nodes with high betweenness centrality that, if removed, would
     fragment the architecture (SPOFs — Single Points of Failure).

  2. Cluster Detection (Weakly Connected Components)
     Identifies isolated subgraphs. More than 1 cluster = disconnected arch.

  3. Critical Path Analysis
     Longest weighted path from any source to any sink node.

  4. Hub Detection
     Nodes with degree centrality > 2× the mean — over-connected nodes
     that violate the Single Responsibility Principle.

  5. Resilience Score
     Aggregate metric: 1 - (bottlenecks / total_nodes).

All results are returned as pydantic AnalyticsResult models and are
also written to the ArchGraphModel.analytics JSON column in PostgreSQL
for caching (re-queried on demand from the frontend).

Usage:
    service = Neo4jAnalyticsService()
    result  = await service.analyse(graph_id="abc-123")
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from apps.backend.core.neo4j import get_neo4j_session
from apps.backend.schemas import (
    AnalyticsBottleneck,
    AnalyticsCluster,
    AnalyticsCriticalPath,
    AnalyticsHub,
    AnalyticsResult,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class Neo4jAnalyticsService:
    """
    Graph analytics service backed by Neo4j Cypher queries.

    Each method executes a single Cypher query within an async driver
    session and returns typed Python objects.

    Graph model in Neo4j:
        (ArchNode {id, label, type, fitness, graph_id})-[:CONNECTS_TO {weight}]->
        (ArchNode {id, label, type, fitness, graph_id})
    """

    # ── Bottleneck detection ───────────────────────────────────────────────────

    async def _get_bottlenecks(self, graph_id: str) -> list[AnalyticsBottleneck]:
        """
        Detect bottleneck nodes using approximated betweenness centrality.

        Cypher heuristic:
          A node is a bottleneck if removing it disconnects more than
          2 other node pairs (i.e. it lies on many shortest paths).
          We approximate this by counting paths that pass through each node.

        Args:
            graph_id: UUID of the architecture graph.

        Returns:
            List of AnalyticsBottleneck objects sorted by severity desc.
        """
        cypher = """
        MATCH (n:ArchNode {graph_id: $graph_id})
        OPTIONAL MATCH (a:ArchNode {graph_id: $graph_id})-[:CONNECTS_TO*..3]->(n)
            -[:CONNECTS_TO*..3]->(b:ArchNode {graph_id: $graph_id})
        WHERE a <> n AND b <> n AND a <> b
        WITH n, count(DISTINCT [a.id, b.id]) AS path_count, n.fitness AS fitness
        WHERE path_count > 2
        RETURN n.id AS nodeId, n.label AS label, n.type AS type,
               path_count, fitness
        ORDER BY path_count DESC
        LIMIT 10
        """
        async with get_neo4j_session() as session:
            result = await session.run(cypher, graph_id=graph_id)
            records = await result.data()

        return [
            AnalyticsBottleneck(
                node_id=   r["nodeId"],
                label=     r["label"],
                node_type= r["type"],
                path_count=r["path_count"],
                severity=  min(1.0, r["path_count"] / 20.0),
            )
            for r in records
        ]

    # ── Cluster detection ──────────────────────────────────────────────────────

    async def _get_clusters(self, graph_id: str) -> list[AnalyticsCluster]:
        """
        Find weakly connected components using BFS-expansion in Cypher.

        Each distinct component is a cluster. More than 1 cluster means
        some nodes are completely isolated from the rest of the architecture.

        Args:
            graph_id: UUID of the architecture graph.

        Returns:
            List of AnalyticsCluster (one per distinct component).
        """
        cypher = """
        MATCH (n:ArchNode {graph_id: $graph_id})
        OPTIONAL MATCH path=(n)-[:CONNECTS_TO*]-(m:ArchNode {graph_id: $graph_id})
        WITH n,
             collect(DISTINCT coalesce(m.id, n.id)) + [n.id] AS reachable
        WITH collect(DISTINCT reachable) AS all_groups
        UNWIND all_groups AS grp
        RETURN grp, size(grp) AS cluster_size
        ORDER BY cluster_size DESC
        LIMIT 20
        """
        async with get_neo4j_session() as session:
            result = await session.run(cypher, graph_id=graph_id)
            records = await result.data()

        # Deduplicate by converting to frozensets
        seen:     set[frozenset[str]] = set()
        clusters: list[AnalyticsCluster] = []
        cluster_id = 0

        for r in records:
            fs = frozenset(r["grp"])
            if fs not in seen:
                seen.add(fs)
                clusters.append(AnalyticsCluster(
                    cluster_id=  int(cluster_id),
                    node_ids=    list(fs),
                    size=        int(r["cluster_size"]),
                    is_isolated= bool(r["cluster_size"] < 3),
                ))
                cluster_id += 1

        return clusters

    # ── Critical path ──────────────────────────────────────────────────────────

    async def _get_critical_path(self, graph_id: str) -> AnalyticsCriticalPath | None:
        """
        Find the longest weighted path through the architecture (critical chain).

        Uses Neo4j's allShortestPaths reversed as a proxy; we take the highest
        accumulated weight path from any source (in-degree 0) to any sink (out-degree 0).

        Args:
            graph_id: UUID of the architecture graph.

        Returns:
            AnalyticsCriticalPath or None if no directed path exists.
        """
        cypher = """
        MATCH (source:ArchNode {graph_id: $graph_id})
        WHERE NOT ()-[:CONNECTS_TO]->(source)
        MATCH (sink:ArchNode  {graph_id: $graph_id})
        WHERE NOT (sink)-[:CONNECTS_TO]->()
        MATCH path = (source)-[:CONNECTS_TO*]->(sink)
        WITH path,
             [n IN nodes(path) | n.id]    AS node_ids,
             [r IN relationships(path) | coalesce(r.weight, 0.5)] AS weights
        WITH path, node_ids,
             reduce(total=0.0, w IN weights | total + w) AS total_weight,
             length(path) AS hops
        ORDER BY total_weight DESC
        LIMIT 1
        RETURN node_ids, total_weight, hops
        """
        async with get_neo4j_session() as session:
            result = await session.run(cypher, graph_id=graph_id)
            records = await result.data()

        if not records:
            return None

        r = records[0]
        return AnalyticsCriticalPath(
            node_ids=     r["node_ids"],
            total_weight= round(r["total_weight"], 4),
            hops=         r["hops"],
            is_long=      r["hops"] > 5,
        )

    # ── Hub detection ──────────────────────────────────────────────────────────

    async def _get_hubs(self, graph_id: str) -> list[AnalyticsHub]:
        """
        Detect hub nodes (over-connected nodes violating SRP).

        A node is a hub if its in+out degree is more than 2× the graph mean.

        Args:
            graph_id: UUID of the architecture graph.

        Returns:
            List of AnalyticsHub, sorted by degree desc.
        """
        cypher = """
        MATCH (n:ArchNode {graph_id: $graph_id})
        OPTIONAL MATCH (n)-[out:CONNECTS_TO]->()
        OPTIONAL MATCH ()-[in:CONNECTS_TO]->(n)
        WITH n, count(DISTINCT out) AS out_deg, count(DISTINCT in) AS in_deg
        WITH n, out_deg + in_deg AS degree
        WITH collect({id: n.id, label: n.label, type: n.type, degree: degree}) AS all_nodes,
             avg(toFloat(out_deg + in_deg)) AS mean_degree
        UNWIND all_nodes AS node
        WHERE node.degree > mean_degree * 2
        RETURN node.id AS nodeId, node.label AS label,
               node.type AS type, node.degree AS degree,
               mean_degree
        ORDER BY degree DESC
        """
        async with get_neo4j_session() as session:
            result = await session.run(cypher, graph_id=graph_id)
            records = await result.data()

        return [
            AnalyticsHub(
                node_id=    r["nodeId"],
                label=      r["label"],
                node_type=  r["type"],
                degree=     int(r["degree"]),
                mean_degree=round(float(r["mean_degree"]), 2),
            )
            for r in records
        ]

    # ── Master analyse ─────────────────────────────────────────────────────────

    async def analyse(self, graph_id: str) -> AnalyticsResult:
        """
        Run all 4 analytics queries in parallel and compute the resilience score.

        Uses asyncio.gather so all 4 Cypher queries execute concurrently
        (each in its own Neo4j session).

        Args:
            graph_id: UUID of the architecture graph to analyse.

        Returns:
            AnalyticsResult with all analytics sub-results.
        """
        logger.info("neo4j_analytics_start", graph_id=graph_id)

        bottlenecks, clusters, critical_path, hubs = await asyncio.gather(
            self._get_bottlenecks(graph_id),
            self._get_clusters(graph_id),
            self._get_critical_path(graph_id),
            self._get_hubs(graph_id),
        )

        # Resilience: penalise for bottlenecks and hub over-concentration
        total_nodes = sum(c.size for c in clusters)
        bottleneck_ratio = len(bottlenecks) / max(total_nodes, 1)
        hub_ratio        = len(hubs) / max(total_nodes, 1)
        resilience_score = max(0.0, 1.0 - bottleneck_ratio * 0.6 - hub_ratio * 0.4)

        result = AnalyticsResult(
            graph_id=        graph_id,
            bottlenecks=     bottlenecks,
            clusters=        clusters,
            critical_path=   critical_path,
            hubs=            hubs,
            resilience_score=round(float(resilience_score), 4),
            cluster_count=   len(clusters),
            bottleneck_count=len(bottlenecks),
        )

        logger.info(
            "neo4j_analytics_complete",
            graph_id=         graph_id,
            resilience=       result.resilience_score,
            bottlenecks=      result.bottleneck_count,
            clusters=         result.cluster_count,
        )
        return result


# ── Module singleton ──────────────────────────────────────────────────────────
analytics_service = Neo4jAnalyticsService()
