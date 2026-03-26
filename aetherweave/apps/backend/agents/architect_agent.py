"""
AetherWeave Backend — ArchitectAgent
======================================

The ArchitectAgent is responsible for analysing the current graph and
proposing structural mutations to improve it.

Role in the LangGraph workflow
-------------------------------
Node name: "architect"
Inputs from state: individual_genome, graph_payload, fitness_scores, intent
Outputs to state: architect_proposal, architect_mutations, agent_messages

Algorithm
---------
1. Analyse the NetworkX graph derived from the current genome.
2. Apply heuristics to identify improvement opportunities:
   a. Bottleneck nodes (single points of failure) → propose split_node
   b. Missing resilience types (no auth, no monitor) → propose add_node
   c. Overloaded ML nodes → propose scale_up
   d. Low-cost graph → propose add_node for more types
3. Format proposals as structured mutation dicts.
4. If an LLM is configured (OPENAI_API_KEY set), enhance with LLM-generated
   rationale. Otherwise, use deterministic rule-based rationale.
5. Return updated state slice.

Deterministic fallback
----------------------
When no LLM key is configured, the agent uses pure graph analysis with
NetworkX to generate proposals. This ensures the system works fully offline.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import networkx as nx
import structlog

from apps.backend.agents.state import AgentState
from apps.backend.services.evolution_service import (
    ALL_NODE_TYPES,
    individual_to_nx,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Node types that every resilient architecture should have
RESILIENCE_TYPES = {"auth", "monitor", "gateway"}


def _format_agent_message(
    role: str,
    content: str,
    confidence: float,
    generation: int,
) -> dict[str, Any]:
    """
    Format a dict matching the AgentMessage interface in types.py.

    Args:
        role:       AgentRole string ("architect", "critic", etc.)
        content:    Message body.
        confidence: Agent self-confidence [0, 1].
        generation: Current evolution generation index.

    Returns:
        Dict matching the AgentMessage TypeScript interface.
    """
    return {
        "role":       role,
        "content":    content,
        "confidence": round(confidence, 3),
        "generation": generation,
        "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
    }


def architect_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node: ArchitectAgent.

    Analyses the current architecture graph and proposes structural mutations.

    Heuristics applied (in order):
    1. Bottleneck detection — if any node has in_degree == out_degree == 1,
       propose split_node to add redundancy.
    2. Missing resilience types — if `auth` or `monitor` are absent, propose
       add_node for the missing types.
    3. Type diversification — if fewer than 4 distinct types exist, propose
       add_node for a randomly selected missing type.
    4. Cost reduction — if aggregate fitness < 0.4 and > 8 costly ML nodes,
       propose scale_down on one ML node.

    Args:
        state: Current shared AgentState from LangGraph.

    Returns:
        Partial state dict with keys:
          - architect_proposal (str)
          - architect_mutations (list of mutation dicts)
          - agent_messages (appended AgentMessage)
    """
    generation = state["generation"]
    genome     = state["individual_genome"]
    fitness    = state["fitness_scores"]

    logger.debug("architect_node_running", generation=generation)

    # Build NetworkX graph for analysis
    G = individual_to_nx(genome)
    n_nodes = G.number_of_nodes()

    proposals: list[dict[str, Any]] = []
    rationale_parts: list[str] = []

    # ── Heuristic 1: Bottleneck detection ─────────────────────────────────
    bottlenecks = [
        node for node in G.nodes()
        if G.in_degree(node) == 1 and G.out_degree(node) == 1
    ]
    if bottlenecks:
        node_idx = random.choice(bottlenecks)
        node_type = G.nodes[node_idx].get("node_type", "service")
        proposals.append({
            "type":      "split_node",
            "node_idx":  node_idx,
            "node_type": node_type,
            "rationale": f"Node {node_idx} ({node_type}) is a single point of failure. "
                         f"Splitting into two parallel instances eliminates this bottleneck.",
        })
        rationale_parts.append(f"detected {len(bottlenecks)} bottleneck node(s)")

    # ── Heuristic 2: Missing resilience types ─────────────────────────────
    present_types = {data.get("node_type") for _, data in G.nodes(data=True)}
    missing_resilience = RESILIENCE_TYPES - present_types

    for missing_type in list(missing_resilience)[:2]:  # Add at most 2 per generation
        proposals.append({
            "type":      "add_node",
            "node_type": missing_type,
            "rationale": f"Architecture lacks a dedicated '{missing_type}' node. "
                         f"Adding one improves resilience and the future_proof score.",
        })
        rationale_parts.append(f"missing '{missing_type}'")

    # ── Heuristic 3: Type diversification ────────────────────────────────
    if len(present_types) < 4 and n_nodes < 15:
        available = [t for t in ALL_NODE_TYPES if t not in present_types]
        if available:
            new_type = random.choice(available)
            proposals.append({
                "type":      "add_node",
                "node_type": new_type,
                "rationale": f"Only {len(present_types)} distinct node types present. "
                             f"Adding '{new_type}' increases architectural diversity.",
            })
            rationale_parts.append("low type diversity")

    # ── Heuristic 4: Cost reduction ──────────────────────────────────────
    if fitness.get("aggregate", 1.0) < 0.4:
        ml_nodes = [i for i, d in G.nodes(data=True) if d.get("node_type") == "ml"]
        if len(ml_nodes) > 2:
            proposals.append({
                "type":      "scale_down",
                "node_idx":  random.choice(ml_nodes),
                "node_type": "ml",
                "rationale": "ML nodes are expensive. Scaling one down reduces cost "
                             "while retaining inference capacity.",
            })
            rationale_parts.append("high ML cost")

    # Default proposal if no heuristics triggered
    if not proposals:
        add_type = random.choice(ALL_NODE_TYPES)
        proposals.append({
            "type":      "add_node",
            "node_type": add_type,
            "rationale": f"Architecture is stable. Exploring a new '{add_type}' node "
                         f"to expand capability.",
        })
        rationale_parts.append("exploratory expansion")

    proposal_text = (
        f"Generation {generation} analysis: {', '.join(rationale_parts)}. "
        f"Proposing {len(proposals)} mutation(s): "
        + "; ".join(
            f"{p['type']} on '{p.get('node_type', 'node')}'"
            for p in proposals
        ) + "."
    )

    confidence = min(0.95, 0.5 + 0.1 * len(proposals))
    msg = _format_agent_message("architect", proposal_text, confidence, generation)

    logger.info(
        "architect_proposals",
        generation=generation,
        proposal_count=len(proposals),
        rationale=rationale_parts,
    )

    return {
        "architect_proposal":  proposal_text,
        "architect_mutations": proposals,
        "agent_messages":      state.get("agent_messages", []) + [msg],
    }
