"""
AetherWeave Backend — Analytics Pydantic Schemas
=================================================

Typed output models for the Neo4j graph analytics service.
These are returned by GET /api/v1/architecture/{id}/analytics.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyticsBottleneck(BaseModel):
    """A node identified as a structural bottleneck (SPOF)."""
    node_id:   str
    label:     str
    node_type: str
    path_count: int   = Field(..., description="Number of shortest paths passing through this node")
    severity:  float  = Field(..., ge=0.0, le=1.0, description="Normalised severity [0,1]")


class AnalyticsCluster(BaseModel):
    """A weakly connected component in the architecture graph."""
    cluster_id:  int
    node_ids:    list[str]
    size:        int
    is_isolated: bool = Field(..., description="True if cluster has < 3 nodes (likely a dangling component)")


class AnalyticsCriticalPath(BaseModel):
    """The longest weighted path from any source to any sink."""
    node_ids:     list[str]
    total_weight: float
    hops:         int
    is_long:      bool = Field(..., description="True if path has > 5 hops (potential latency concern)")


class AnalyticsHub(BaseModel):
    """A node with degree > 2× the graph mean (over-connected)."""
    node_id:     str
    label:       str
    node_type:   str
    degree:      int
    mean_degree: float


class AnalyticsResult(BaseModel):
    """Complete analytics result for one architecture graph."""
    graph_id:         str
    bottlenecks:      list[AnalyticsBottleneck]
    clusters:         list[AnalyticsCluster]
    critical_path:    AnalyticsCriticalPath | None
    hubs:             list[AnalyticsHub]
    resilience_score: float = Field(..., ge=0.0, le=1.0)
    cluster_count:    int
    bottleneck_count: int


# ── Pareto front schemas ──────────────────────────────────────────────────────

class ParetoIndividual(BaseModel):
    """One Pareto-optimal individual from the NSGA-II Pareto front."""
    rank:           int
    scalability:    float
    cost_efficiency: float
    future_proof:   float
    aggregate:      float
    generation:     int
    node_count:     int


class ParetoFrontResult(BaseModel):
    """Pareto front results for the current evolution run."""
    graph_id:    str
    individuals: list[ParetoIndividual]
    front_size:  int
    dominated:   int   = Field(..., description="Number of solutions dominated (not on front)")
