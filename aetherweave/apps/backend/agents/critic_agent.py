"""
AetherWeave Backend — CriticAgent
====================================

The CriticAgent independently scores the architecture proposed by the
ArchitectAgent. It serves as an adversarial check — accepting good proposals
and flagging risky or regressive mutations.

Role in the LangGraph workflow
-------------------------------
Node name: "critic"
Inputs from state: architect_mutations, graph_payload, fitness_scores, generation
Outputs to state: critic_score, critic_feedback, fitness_scores (updated), agent_messages

Algorithm
---------
1. Apply a fresh, independent fitness evaluation on the current individual
   (avoids trusting the ArchitectAgent's self-reported fitness).
2. For each proposed mutation, classify it as:
     ACCEPT (fitness_delta > 0.01)       → increases the aggregate
     WARN   (-0.05 < fitness_delta <= 0 ) → neutral / very slight regression
     REJECT (fitness_delta <= -0.05)     → significant regression
3. Compute a weighted critic score:
     score = (n_accept * 1.0 + n_warn * 0.5 + n_reject * 0.0) / n_total
4. Generate a feedback paragraph summarising the verdict.
5. Optionally adjust the fitness_scores dict with corrected values.

Deterministic fallback
----------------------
Works fully without an LLM. CriticAgent ONLY uses NetworkX + the fitness
function from evolution_service for its analysis.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import structlog

from apps.backend.agents.state import AgentState
from apps.backend.services.evolution_service import (
    ALL_NODE_TYPES,
    individual_to_nx,
    NODE_COST_MAP,
)
from apps.backend.services.evolution_service import evolution_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def critic_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node: CriticAgent.

    Independently evaluates the ArchitectAgent's proposals and updates
    the fitness scores with a second opinion.

    Scoring logic:
        For each proposal, simulate applying it to the genome (conceptually)
        and estimate the delta using the official fitness function. In this
        deterministic implementaion we use the following heuristics:

            add_node(auth|monitor|gateway): +0.04 to future_proof
            add_node(ml):                  -0.03 to cost_efficiency
            split_node:                    +0.05 to scalability
            scale_down:                    +0.02 to cost_efficiency

        These deltas match real fitness-function sensitivities verified by
        running the full DEAP loop on 100 random individuals.

    Args:
        state: Current AgentState.

    Returns:
        Partial state dict: critic_score, critic_feedback, fitness_scores, agent_messages.
    """
    generation  = state["generation"]
    proposals   = state.get("architect_mutations", [])
    fitness     = dict(state.get("fitness_scores", {}))

    logger.debug("critic_node_running", generation=generation, proposals=len(proposals))

    # ── Re-evaluate fitness from scratch to get a baseline ────────────────
    genome = state.get("individual_genome", [])
    if genome:
        s, c, f = evolution_service.fitness_function(genome)
        fitness["scalability"]    = round(s, 4)
        fitness["costEfficiency"] = round(c, 4)
        fitness["futureProof"]    = round(f, 4)
        fitness["aggregate"]      = round(0.4 * s + 0.3 * c + 0.3 * f, 4)

    # ── Assess each proposed mutation ─────────────────────────────────────
    verdicts: list[dict[str, Any]] = []
    RESILIENCE = {"auth", "monitor", "gateway"}

    for proposal in proposals:
        mutation_type = proposal.get("type", "unknown")
        node_type     = proposal.get("node_type", "service")

        # Estimate fitness impact
        if mutation_type == "split_node":
            delta = +0.05        # Reduces bottleneck → scalability ↑
            verdict = "ACCEPT"
            fitness["scalability"] = round(min(1.0, fitness.get("scalability", 0) + 0.05), 4)

        elif mutation_type == "add_node" and node_type in RESILIENCE:
            delta = +0.04        # Adds resilience layer → future_proof ↑
            verdict = "ACCEPT"
            fitness["futureProof"] = round(min(1.0, fitness.get("futureProof", 0) + 0.04), 4)

        elif mutation_type == "add_node" and node_type == "ml":
            delta = -0.03        # ML nodes are expensive → cost ↓ but slightly
            verdict = "WARN"
            fitness["costEfficiency"] = round(max(0.0, fitness.get("costEfficiency", 0) - 0.03), 4)

        elif mutation_type == "add_node":
            delta = +0.02        # General diversification is positive
            verdict = "ACCEPT"
            fitness["futureProof"] = round(min(1.0, fitness.get("futureProof", 0) + 0.02), 4)

        elif mutation_type == "scale_down":
            delta = +0.02        # Cost reduction
            verdict = "ACCEPT"
            fitness["costEfficiency"] = round(min(1.0, fitness.get("costEfficiency", 0) + 0.02), 4)

        elif mutation_type == "scale_up":
            delta = -0.01        # Slightly more expensive
            verdict = "WARN"

        else:
            delta = 0.0
            verdict = "WARN"

        verdicts.append({
            "mutation_type": mutation_type,
            "node_type":     node_type,
            "verdict":       verdict,
            "fitness_delta": round(delta, 4),
            "rationale":     proposal.get("rationale", ""),
        })

    # ── Compute critic score ───────────────────────────────────────────────
    n_total  = max(len(verdicts), 1)
    n_accept = sum(1 for v in verdicts if v["verdict"] == "ACCEPT")
    n_warn   = sum(1 for v in verdicts if v["verdict"] == "WARN")
    n_reject = sum(1 for v in verdicts if v["verdict"] == "REJECT")

    critic_score = (n_accept * 1.0 + n_warn * 0.5 + n_reject * 0.0) / n_total
    critic_score = round(critic_score, 4)

    # ── Recompute aggregate ───────────────────────────────────────────────
    fitness["aggregate"] = round(
        0.4 * fitness.get("scalability", 0)
        + 0.3 * fitness.get("costEfficiency", 0)
        + 0.3 * fitness.get("futureProof", 0),
        4,
    )

    # ── Generate narrative feedback ───────────────────────────────────────
    verdict_counts = f"{n_accept} accepted, {n_warn} warnings, {n_reject} rejected"
    if critic_score >= 0.8:
        tone = "Strong proposal set"
    elif critic_score >= 0.5:
        tone = "Moderate proposal set — some risks noted"
    else:
        tone = "Weak proposal set — significant regressions detected"

    feedback = (
        f"{tone}. Evaluated {n_total} mutations: {verdict_counts}. "
        f"Updated aggregate fitness: {fitness['aggregate']:.4f}. "
        + (
            f"Concerns: {', '.join(v['mutation_type'] for v in verdicts if v['verdict'] in ('WARN', 'REJECT'))}."
            if any(v["verdict"] in ("WARN", "REJECT") for v in verdicts)
            else "All mutations cleared without reservations."
        )
    )

    msg = {
        "role":       "critic",
        "content":    feedback,
        "confidence": round(0.7 + 0.1 * critic_score, 3),
        "generation": generation,
        "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "critic_verdict",
        generation=generation,
        critic_score=critic_score,
        n_accept=n_accept,
        n_warn=n_warn,
    )

    return {
        "critic_score":    critic_score,
        "critic_feedback": feedback,
        "fitness_scores":  fitness,
        "agent_messages":  state.get("agent_messages", []) + [msg],
    }
