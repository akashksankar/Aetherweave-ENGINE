"""Initial database migration — creates all AetherWeave tables.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-26
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all AetherWeave tables in dependency order."""

    # ── arch_graphs ───────────────────────────────────────────────────────────
    op.create_table(
        "arch_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("intent", sa.Text, nullable=False),
        sa.Column("generation", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fitness_scalability", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("fitness_cost_efficiency", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("fitness_future_proof", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("fitness_aggregate", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("is_evolving", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("celery_task_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── arch_nodes ────────────────────────────────────────────────────────────
    op.create_table(
        "arch_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("pos_x", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("pos_y", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("pos_z", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("fitness", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("generation", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ancestry", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["graph_id"], ["arch_graphs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_arch_nodes_graph_id", "arch_nodes", ["graph_id"])

    # ── arch_edges ────────────────────────────────────────────────────────────
    op.create_table(
        "arch_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("label", sa.String(50), nullable=False, server_default="HTTP"),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.ForeignKeyConstraint(["graph_id"], ["arch_graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["arch_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["arch_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_arch_edges_graph_id", "arch_edges", ["graph_id"])

    # ── evolution_runs ────────────────────────────────────────────────────────
    op.create_table(
        "evolution_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("generations_requested", sa.Integer, nullable=False),
        sa.Column("generations_run", sa.Integer, nullable=False, server_default="0"),
        sa.Column("population_size", sa.Integer, nullable=False),
        sa.Column("enable_debate", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("final_fitness", sa.Float, nullable=True),
        sa.Column("fitness_history", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["graph_id"], ["arch_graphs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evolution_runs_graph_id", "evolution_runs", ["graph_id"])

    # ── mutations ─────────────────────────────────────────────────────────────
    op.create_table(
        "mutations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evolution_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("mutation_type", sa.String(50), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fitness_delta", sa.Float, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["graph_id"], ["arch_graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evolution_run_id"], ["evolution_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mutations_graph_id", "mutations", ["graph_id"])

    # ── symbiosis_tokens ──────────────────────────────────────────────────────
    op.create_table(
        "symbiosis_tokens",
        sa.Column("token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shared_node_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("used", sa.Boolean, nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["graph_id"], ["arch_graphs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index("ix_symbiosis_tokens_graph_id", "symbiosis_tokens", ["graph_id"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("symbiosis_tokens")
    op.drop_table("mutations")
    op.drop_table("evolution_runs")
    op.drop_table("arch_edges")
    op.drop_table("arch_nodes")
    op.drop_table("arch_graphs")
