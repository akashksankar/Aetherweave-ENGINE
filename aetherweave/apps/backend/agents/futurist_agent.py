"""
AetherWeave Backend — FuturistAgent with Monte-Carlo Temporal Foresight
=========================================================================

The FuturistAgent simulates the architecture's survivability over 2–5 years
using a Monte-Carlo model. It stochastically generates N scenarios with
randomised technology trends and computes what fraction of them the
current architecture can handle.

Monte-Carlo model
-----------------
Each simulation trial:
  1. Sample a random "trend event" from a weighted catalogue.
  2. Check if the current architecture has the node types needed to adapt.
  3. Record survival (True) or failure (False).

After N=500 trials per time horizon:
  survival_rate(t) = count(survived) / N

future_proof_score = mean(survival_rate over t in [2, 3, 4, 5] years)
                   = Σ survival_rate(t) / 4

Trend event catalogue
----------------------
The catalogue models real technology disruption patterns observed in
enterprise architecture evolution:
  - cloud_migration:     needs 'cdn' + 'cache'
  - ml_adoption:         needs 'ml'
  - zero_trust_security: needs 'auth' + 'gateway'
  - edge_computing:      needs 'edge'
  - real_time_streaming: needs 'queue' + 'cache'
  - cost_optimisation:   needs 'monitor'
  - global_expansion:    needs 'cdn' + 'edge'
  - ai_inference_surge:  needs 'ml' + 'cache'

Each event also has a probability (weight) reflecting how likely it is
to become a dominant trend in the simulated time horizon.
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from apps.backend.agents.state import AgentState
from apps.backend.services.evolution_service import individual_to_nx

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Monte-Carlo parameters ─────────────────────────────────────────────────────

N_TRIALS = 500       # Trials per time horizon
TIME_HORIZONS = [2, 3, 4, 5]  # Years to simulate

# ── Tech trend catalogue ───────────────────────────────────────────────────────
# Each entry: (event_name, [required_node_types], probability_weight)

TREND_CATALOGUE: list[tuple[str, list[str], float]] = [
    ("cloud_migration",      ["cdn", "cache"],          0.15),
    ("ml_adoption",          ["ml"],                    0.12),
    ("zero_trust_security",  ["auth", "gateway"],       0.13),
    ("edge_computing",       ["edge"],                  0.08),
    ("real_time_streaming",  ["queue", "cache"],        0.14),
    ("cost_optimisation",    ["monitor"],               0.10),
    ("global_expansion",     ["cdn", "edge"],           0.11),
    ("ai_inference_surge",   ["ml", "cache"],           0.10),
    ("serverless_transition", ["gateway"],              0.07),
]

TREND_NAMES   = [t[0] for t in TREND_CATALOGUE]
TREND_REQS    = [t[1] for t in TREND_CATALOGUE]
TREND_WEIGHTS = np.array([t[2] for t in TREND_CATALOGUE])
TREND_WEIGHTS /= TREND_WEIGHTS.sum()  # normalise to sum=1


def _simulate_horizon(present_types: set[str], horizon_years: int) -> float:
    """
    Run N_TRIALS Monte-Carlo trials for a single time horizon.

    For each trial:
      1. Sample between 1 and min(horizon_years, 3) concurrent trend events.
      2. The architecture "survives" if it has at least one required node type
         for every sampled trend (partial coverage is sufficient — assumes
         ability to extend rather than needing perfect coverage upfront).

    Args:
        present_types: Set of node type strings present in the architecture.
        horizon_years: Time horizon in years (2, 3, 4, or 5).

    Returns:
        Survival rate in [0, 1] (fraction of trials survived).
    """
    n_survived = 0
    n_events   = min(horizon_years, 3)  # More events as time horizon grows

    for _ in range(N_TRIALS):
        # Sample N concurrent trend events (with replacement)
        event_indices = np.random.choice(
            len(TREND_CATALOGUE), size=n_events, p=TREND_WEIGHTS, replace=False
        )
        # Survive if at least one required type is present for each trend
        survived = all(
            any(req in present_types for req in TREND_REQS[i])
            for i in event_indices
        )
        if survived:
            n_survived += 1

    return n_survived / N_TRIALS


def futurist_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node: FuturistAgent.

    Runs a Monte-Carlo temporal foresight simulation and updates the
    future_proof fitness score based on the results.

    The simulation tests the architecture against stochastic technology
    trend events over a 2–5 year horizon. Each horizon yields a survival
    rate; the mean of all horizon rates becomes the new future_proof score.

    Args:
        state: Current AgentState (reads individual_genome, generation, fitness_scores).

    Returns:
        Partial state dict:
          - futurist_risk_report (str narrative)
          - futurist_future_proof_score (float)
          - fitness_scores (updated futureProof + aggregate)
          - agent_messages (appended)
    """
    generation = state["generation"]
    genome     = state.get("individual_genome", [])
    fitness    = dict(state.get("fitness_scores", {}))

    logger.debug("futurist_node_running", generation=generation)

    # Extract present node types from genome
    G = individual_to_nx(genome)
    present_types: set[str] = {
        data.get("node_type", "service")
        for _, data in G.nodes(data=True)
    }

    # ── Run Monte-Carlo per time horizon ──────────────────────────────────
    horizon_results: dict[int, float] = {}
    for years in TIME_HORIZONS:
        survival = _simulate_horizon(present_types, years)
        horizon_results[years] = round(survival, 4)

    future_proof_score = round(
        sum(horizon_results.values()) / len(TIME_HORIZONS), 4
    )

    # ── Identify top risks ────────────────────────────────────────────────
    risk_trends: list[str] = []
    for trend_name, req_types, _ in TREND_CATALOGUE:
        if not any(rt in present_types for rt in req_types):
            risk_trends.append(f"'{trend_name}' (needs: {', '.join(req_types)})")

    # ── Generate narrative report ─────────────────────────────────────────
    horizon_summary = "  ".join(
        f"Y{yr}: {rate:.0%}" for yr, rate in sorted(horizon_results.items())
    )

    if future_proof_score >= 0.75:
        outlook = "Strong temporal resilience"
    elif future_proof_score >= 0.50:
        outlook = "Moderate survivability — some gaps"
    else:
        outlook = "High temporal risk — critical adaptations needed"

    risk_section = (
        f"Critical gaps: {'; '.join(risk_trends[:3])}."
        if risk_trends
        else "No critical coverage gaps detected."
    )

    report = (
        f"{outlook}. Survival rates over {N_TRIALS} Monte-Carlo trials: {horizon_summary}. "
        f"Composite future_proof score: {future_proof_score:.4f}. "
        f"{risk_section}"
    )

    # ── Update fitness scores ─────────────────────────────────────────────
    fitness["futureProof"] = future_proof_score
    fitness["aggregate"] = round(
        0.4 * fitness.get("scalability", 0)
        + 0.3 * fitness.get("costEfficiency", 0)
        + 0.3 * future_proof_score,
        4,
    )

    msg = {
        "role":       "futurist",
        "content":    report,
        "confidence": round(0.6 + 0.3 * future_proof_score, 3),
        "generation": generation,
        "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "futurist_simulation_complete",
        generation=generation,
        future_proof=future_proof_score,
        horizon_results=horizon_results,
    )

    return {
        "futurist_risk_report":         report,
        "futurist_future_proof_score":  future_proof_score,
        "fitness_scores":               fitness,
        "agent_messages":               state.get("agent_messages", []) + [msg],
    }
