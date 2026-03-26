"""
AetherWeave Backend — SQLAlchemy ORM Models
============================================

Defines all PostgreSQL tables used by AetherWeave:

  arch_graphs     — Stores top-level graph metadata (name, generation, fitness).
  arch_nodes      — Stores individual nodes belonging to a graph.
  arch_edges      — Stores directed edges between nodes.
  mutations       — Full audit log of every evolutionary mutation.
  evolution_runs  — Records each complete evolution job (started, duration, result).
  symbiosis_tokens — Secure share tokens for the DNA-sharing feature.

Design decisions:
  - UUID primary keys everywhere (avoids sequential ID enumeration attacks).
  - All timestamps are UTC stored as TIMESTAMPTZ.
  - JSON columns for flexible metadata (avoids ALTER TABLE for every new field).
  - `arch_nodes` stores fitness + generation for quick leaderboard queries
    without joining the full graph.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.core.database import Base


# ─── Utility ──────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    """Return the current UTC time (used as column default)."""
    return datetime.now(tz=timezone.utc)


def _new_uuid() -> uuid.UUID:
    """Generate a new UUID v4 (used as column default)."""
    return uuid.uuid4()


# ─── ArchGraph ────────────────────────────────────────────────────────────────


class ArchGraphModel(Base):
    """
    PostgreSQL table: arch_graphs

    Stores the top-level metadata for each architecture graph.
    The actual node/edge topology lives in both this table (via relationships)
    AND in Neo4j (for graph-query efficiency).

    Each row represents one "living" architecture that can be evolved over time.
    """

    __tablename__ = "arch_graphs"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )

    # ── Basic metadata ────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        doc="User-chosen display name for this architecture."
    )
    intent: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="Original natural-language intent string provided by the user."
    )
    generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        doc="Current evolutionary generation counter."
    )

    # ── Fitness scores (denormalised for fast ORDER BY queries) ───────────────
    fitness_scalability: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        doc="Scalability score [0, 1]; see FitnessScore in types.py."
    )
    fitness_cost_efficiency: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        doc="Cost efficiency score [0, 1]."
    )
    fitness_future_proof: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        doc="Future-proof score [0, 1] from Monte-Carlo simulation."
    )
    fitness_aggregate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        doc="Weighted aggregate fitness = 0.4*scale + 0.3*cost + 0.3*future."
    )

    # ── Evolution state ────────────────────────────────────────────────────────
    is_evolving: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="True while a Celery evolution job is actively running."
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        doc="ID of the active Celery task, if any."
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    nodes: Mapped[list["ArchNodeModel"]] = relationship(
        "ArchNodeModel", back_populates="graph",
        cascade="all, delete-orphan", lazy="selectin"
    )
    edges: Mapped[list["ArchEdgeModel"]] = relationship(
        "ArchEdgeModel", back_populates="graph",
        cascade="all, delete-orphan", lazy="selectin"
    )
    evolution_runs: Mapped[list["EvolutionRunModel"]] = relationship(
        "EvolutionRunModel", back_populates="graph",
        cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<ArchGraph id={self.id} name={self.name!r} gen={self.generation}>"


# ─── ArchNode ─────────────────────────────────────────────────────────────────


class ArchNodeModel(Base):
    """
    PostgreSQL table: arch_nodes

    Each row is one node in an architecture graph.
    Mirrors ArchNode in types.py with the addition of FK to arch_graphs.
    """

    __tablename__ = "arch_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_graphs.id", ondelete="CASCADE"), nullable=False,
        index=True, doc="Owning graph."
    )

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, doc="NodeType enum value.")

    # 3D position
    pos_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pos_z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    fitness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Ancestry stored as a JSON array of UUID strings
    ancestry: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict,
        doc="Freeform JSON from ArchitectAgent."
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    graph: Mapped["ArchGraphModel"] = relationship("ArchGraphModel", back_populates="nodes")

    def __repr__(self) -> str:
        return f"<ArchNode id={self.id} label={self.label!r} type={self.node_type}>"


# ─── ArchEdge ─────────────────────────────────────────────────────────────────


class ArchEdgeModel(Base):
    """PostgreSQL table: arch_edges — directed edges between nodes."""

    __tablename__ = "arch_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_graphs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_nodes.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_nodes.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="HTTP")
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    graph: Mapped["ArchGraphModel"] = relationship("ArchGraphModel", back_populates="edges")


# ─── Mutation ─────────────────────────────────────────────────────────────────


class MutationModel(Base):
    """
    PostgreSQL table: mutations

    Full audit log of every genetic operation applied during evolution.
    Enables reconstruction of the complete evolution lineage tree.
    """

    __tablename__ = "mutations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_graphs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    evolution_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evolution_runs.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    mutation_type: Mapped[str] = mapped_column(String(50), nullable=False, doc="MutationType value.")
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    partner_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    fitness_delta: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    def __repr__(self) -> str:
        return f"<Mutation id={self.id} type={self.mutation_type} gen={self.generation}>"


# ─── EvolutionRun ─────────────────────────────────────────────────────────────


class EvolutionRunModel(Base):
    """
    PostgreSQL table: evolution_runs

    Records each complete evolution job — one row per call to POST /evolve.
    Tracks status (running/complete/failed), duration, and the serialised result.
    """

    __tablename__ = "evolution_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_graphs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        doc="One of: pending | running | complete | failed."
    )
    generations_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    generations_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    population_size: Mapped[int] = mapped_column(Integer, nullable=False)
    enable_debate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Summary fitness for the completed run
    final_fitness: Mapped[float | None] = mapped_column(Float, nullable=True)
    fitness_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Duration
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    graph: Mapped["ArchGraphModel"] = relationship("ArchGraphModel", back_populates="evolution_runs")

    def __repr__(self) -> str:
        return f"<EvolutionRun id={self.id} status={self.status} graph={self.graph_id}>"


# ─── SymbiosisToken ───────────────────────────────────────────────────────────


class SymbiosisTokenModel(Base):
    """
    PostgreSQL table: symbiosis_tokens

    Secure one-time share tokens for the DNA-borrowing feature.
    The token UUID is the public-facing identifier; the graph_id is never exposed.
    """

    __tablename__ = "symbiosis_tokens"

    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_new_uuid)
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arch_graphs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    shared_node_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
