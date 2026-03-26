"""
AetherWeave Shared Python Types
================================
Mirror of packages/shared/types.ts — keep both files in sync manually
(or use the code-gen script in packages/shared/codegen.py).

Every class is a Pydantic v2 BaseModel with full field documentation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ─── Enums ───────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    """Semantic role of an architecture node. Maps to Neo4j node labels."""
    SERVICE = "service"
    DATABASE = "database"
    GATEWAY = "gateway"
    CACHE = "cache"
    QUEUE = "queue"
    CDN = "cdn"
    AUTH = "auth"
    MONITOR = "monitor"
    ML = "ml"
    EDGE = "edge"


class MutationType(str, Enum):
    """Genetic operation applied to a node during an evolution step."""
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    MERGE_NODES = "merge_nodes"
    SPLIT_NODE = "split_node"
    CHANGE_TYPE = "change_type"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


class AgentRole(str, Enum):
    """LangGraph swarm agent roles."""
    ARCHITECT = "architect"
    CRITIC = "critic"
    FUTURIST = "futurist"
    DEBATER = "debater"


class ServiceStatus(str, Enum):
    """Simple up/down status for each backing service."""
    UP = "up"
    DOWN = "down"


class SystemHealthStatus(str, Enum):
    """Overall system health roll-up."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ─── Core Entities ───────────────────────────────────────────────────────────


class Position3D(BaseModel):
    """3D world-space coordinates for a node in the loom canvas."""

    x: float = Field(..., ge=-100.0, le=100.0, description="Horizontal axis [-100, 100]")
    y: float = Field(..., ge=-100.0, le=100.0, description="Vertical axis [-100, 100]")
    z: float = Field(..., ge=-100.0, le=100.0, description="Depth axis [-100, 100]")


class FitnessScore(BaseModel):
    """
    Multi-objective fitness score for an architecture.

    Mathematical derivation
    -----------------------
    aggregate = 0.4 * scalability + 0.3 * cost_efficiency + 0.3 * future_proof

    All individual scores must be in [0, 1] where 1.0 is ideal.
    """

    scalability: float = Field(
        ..., ge=0.0, le=1.0,
        description="Derived from graph diameter, fan-out ratios, and bottleneck count."
    )
    cost_efficiency: float = Field(
        ..., ge=0.0, le=1.0,
        description="Inverted cost index: lower infrastructure cost → higher score."
    )
    future_proof: float = Field(
        ..., ge=0.0, le=1.0,
        description="Monte-Carlo predicted adaptability score over a 2-5 year horizon."
    )
    aggregate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Weighted mean of the three dimensions."
    )

    @model_validator(mode="after")
    def validate_aggregate(self) -> "FitnessScore":
        """Ensure aggregate matches the formula within floating-point tolerance."""
        expected = 0.4 * self.scalability + 0.3 * self.cost_efficiency + 0.3 * self.future_proof
        if abs(self.aggregate - expected) > 1e-4:
            raise ValueError(
                f"aggregate {self.aggregate:.4f} does not match formula result {expected:.4f}"
            )
        return self


class ArchNode(BaseModel):
    """
    A single node in the 3D architecture loom.

    Stored in both PostgreSQL (metadata) and Neo4j (graph relationships).
    The `id` is the primary key in both stores.
    """

    id: UUID = Field(..., description="UUID v4 primary key")
    label: str = Field(..., min_length=1, max_length=100, description="Display name")
    type: NodeType = Field(..., description="Semantic node role")
    position: Position3D = Field(..., description="3D canvas world-space coordinates")
    fitness: float = Field(..., ge=0.0, le=1.0, description="Normalised fitness [0, 1]")
    generation: int = Field(..., ge=0, description="Generation in which this node appeared")
    ancestry: list[str] = Field(
        default_factory=list,
        description="Ordered list of ancestor node IDs (oldest first)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Freeform data from the ArchitectAgent"
    )


class ArchEdge(BaseModel):
    """
    A directed dependency edge between two ArchNodes.
    Rendered as a glowing mycelium tube in the 3D loom.
    """

    id: UUID = Field(..., description="UUID v4 edge identifier")
    source: UUID = Field(..., description="Source node ID")
    target: UUID = Field(..., description="Target node ID")
    weight: float = Field(..., ge=0.0, le=1.0, description="Traffic / coupling strength [0, 1]")
    label: str = Field(..., max_length=50, description="Protocol label (e.g. HTTP, gRPC)")
    latency_ms: float | None = Field(None, ge=0.0, description="Estimated latency in milliseconds")


class ArchGraph(BaseModel):
    """
    A complete architectural graph — the primary data structure of AetherWeave.
    Nodes and edges together form a directed graph evaluated by the fitness function.
    """

    id: UUID = Field(..., description="Graph UUID (matches Neo4j graph ID)")
    name: str = Field(..., min_length=1, max_length=200, description="User-chosen display name")
    nodes: list[ArchNode] = Field(default_factory=list, description="All nodes in this graph")
    edges: list[ArchEdge] = Field(default_factory=list, description="All directed edges")
    fitness: FitnessScore = Field(..., description="Multi-objective fitness aggregate")
    generation: int = Field(0, ge=0, description="Current generation counter")
    created_at: datetime = Field(..., description="ISO-8601 creation time")
    updated_at: datetime = Field(..., description="ISO-8601 last update time")


# ─── Mutation & Evolution ────────────────────────────────────────────────────


class Mutation(BaseModel):
    """
    A single recorded mutation event in the evolution history.
    Used to reconstruct the full lineage tree in the loom canvas.
    """

    id: UUID = Field(..., description="Mutation event UUID")
    generation: int = Field(..., ge=0, description="Generation when mutation occurred")
    type: MutationType = Field(..., description="Genetic operation applied")
    node_id: UUID = Field(..., description="Primary node affected")
    partner_node_id: UUID | None = Field(None, description="Second node for merge/crossover")
    fitness_delta: float = Field(
        ...,
        description="Change in aggregate fitness caused by this mutation (may be negative)"
    )
    timestamp: datetime = Field(..., description="When the mutation was applied")
    rationale: str = Field(
        ..., max_length=1000,
        description="Human-readable explanation from the ArchitectAgent"
    )


class EvolutionResult(BaseModel):
    """
    Complete response after running N evolutionary generations.
    Includes the optimal architecture found, full mutation log, and agent debate.
    """

    best_graph: ArchGraph = Field(..., description="Highest-fitness architecture discovered")
    mutations: list[Mutation] = Field(
        default_factory=list, description="All mutation events in chronological order"
    )
    fitness_history: list[float] = Field(
        default_factory=list,
        description="Aggregate fitness per generation (index = generation number)"
    )
    duration_ms: float = Field(..., ge=0.0, description="Total wall-clock time in milliseconds")
    generations_run: int = Field(..., ge=0, description="Actual generations executed")
    agent_debate: list["AgentMessage"] = Field(
        default_factory=list,
        description="Full agent debate transcript for the final generation"
    )


# ─── Symbiosis / DNA Sharing ─────────────────────────────────────────────────


class SymbiosisToken(BaseModel):
    """
    Secure share token for exporting a partial graph to another user.
    The token itself is opaque — it does not expose the internal graph ID.
    """

    token: UUID = Field(..., description="Opaque share token (UUID v4, not the graph ID)")
    graph_id: UUID = Field(..., description="Internal graph being shared")
    shared_node_ids: list[UUID] = Field(
        ..., description="Subset of node IDs included in this share"
    )
    expires_at: datetime = Field(..., description="Token expiry time")
    password_hash: str | None = Field(None, description="bcrypt hash if password-protected")


# ─── Multi-Agent ─────────────────────────────────────────────────────────────


class AgentMessage(BaseModel):
    """A single message produced by an LLM agent during the debate cycle."""

    role: AgentRole = Field(..., description="Which agent produced this message")
    content: str = Field(..., description="Message body (markdown permitted)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent self-confidence [0, 1]")
    generation: int = Field(..., ge=0, description="Generation when produced")
    timestamp: datetime = Field(..., description="UTC timestamp")


# ─── WebSocket Events ────────────────────────────────────────────────────────


class WSGenerationEvent(BaseModel):
    """Emitted once per generation with full updated graph state."""
    type: str = Field("generation", const=True)
    generation: int
    graph: ArchGraph
    fitness: FitnessScore


class WSMutationEvent(BaseModel):
    """Emitted for each individual mutation within a generation."""
    type: str = Field("mutation", const=True)
    mutation: Mutation


class WSAgentEvent(BaseModel):
    """Emitted when an agent publishes a debate message."""
    type: str = Field("agent_message", const=True)
    message: AgentMessage


class WSCompleteEvent(BaseModel):
    """Emitted when the full evolution run finishes."""
    type: str = Field("complete", const=True)
    result: EvolutionResult


class WSErrorEvent(BaseModel):
    """Emitted on any backend error during evolution."""
    type: str = Field("error", const=True)
    code: str
    message: str


# ─── API Schemas ─────────────────────────────────────────────────────────────


class CreateArchitectureRequest(BaseModel):
    """Request body for POST /api/v1/architecture/create"""

    intent: str = Field(
        ..., min_length=5, max_length=2000,
        description="Natural-language description of the desired architecture"
    )
    seed: int | None = Field(None, description="RNG seed for reproducible generation")
    initial_nodes: int = Field(
        8, ge=3, le=50,
        description="Desired initial node count before evolution begins"
    )


class EvolveRequest(BaseModel):
    """Request body for POST /api/v1/evolve"""

    architecture_id: UUID = Field(..., description="ID of the graph to evolve")
    generations: int = Field(
        10, ge=1, le=500,
        description="Number of evolutionary generations to run"
    )
    population_size: int = Field(
        20, ge=10, le=200,
        description="DEAP population size per generation"
    )
    enable_debate: bool = Field(
        True, description="Whether agents debate each generation (slower but richer)"
    )


class ServicesHealth(BaseModel):
    """Health status of each backing service."""
    postgres: ServiceStatus
    neo4j: ServiceStatus
    redis: ServiceStatus
    celery: ServiceStatus


class SystemStatus(BaseModel):
    """Full system health response for GET /api/v1/status"""

    status: SystemHealthStatus
    version: str = Field(..., description="Backend application version")
    uptime: float = Field(..., ge=0.0, description="Process uptime in seconds")
    services: ServicesHealth
    active_evolutions: int = Field(..., ge=0, description="Currently running evolution jobs")
    total_architectures: int = Field(..., ge=0, description="Total graphs stored in the database")
