"""
AetherWeave Backend — DebaterAgent (Echo Agent Swarm)
======================================================

The DebaterAgent runs an internal Echo Agent debate. Three stateless
"stance agents" argue for/against the ArchitectAgent's proposal, then a
consensus function determines the final verdict.

Echo Agent stances
-----------------
  OPTIMIST   — argues for accepting the proposal (emphasises benefits)
  PESSIMIST  — argues against (emphasises risks and downsides)
  PRAGMATIST — looks for a middle ground (proposes modifications)

Debate protocol
--------------
Round 1: Each stance agent produces an opening argument.
Round 2: Each agent responds to the others' Round 1 arguments.
Vote: Each agent casts a vote (ACCEPT / REJECT / MODIFY).
Consensus: If 2+ votes agree → consensus=True; otherwise → False.

This models how real architecture review boards work — competing
perspectives lead to more robust final decisions.

All text is deterministic (no LLM) using templated arguments seeded
by the critic_score and futurist_future_proof_score from state.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import structlog

from apps.backend.agents.state import AgentState

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── Argument templates ─────────────────────────────────────────────────────────
# { score_range: (0.0, 0.5) / (0.5, 0.8) / (0.8, 1.0) → template string }

OPTIMIST_ARGS = [
    "This proposal significantly improves the aggregate fitness by expanding architectural capacity.",
    "The critic validated {accept_count} mutations as beneficial. We should proceed.",
    "Monte-Carlo shows {future_proof:.0%} survivability — above industry average. Accept.",
    "Adding resilience nodes now is cheaper than retrofitting post-failure.",
]

PESSIMIST_ARGS = [
    "The cost efficiency score ({cost:.4f}) is low. Adding nodes increases operational burden.",
    "Only {accept_count} out of {total_mutations} mutations were accepted. Risk is too high.",
    "Monte-Carlo futures show uncertainty. We should not bet on unproven trends.",
    "Increasing complexity without proof of scalability gain is premature optimisation.",
]

PRAGMATIST_ARGS = [
    "Accept the resilience-type additions, but defer ML cost increases to next generation.",
    "Apply split_node mutations only if aggregate fitness > 0.5. Current: {aggregate:.4f}.",
    "A phased adoption: accept {accept_count} mutations now, queue the rest for G+2.",
    "Compromise: add auth/monitor nodes, defer edge and CDN nodes until fitness stabilises.",
]

VOTE_THRESHOLDS = {
    "OPTIMIST":   0.5,   # Votes ACCEPT if critic_score >= 0.5
    "PESSIMIST":  0.75,  # Votes ACCEPT only if critic_score >= 0.75
    "PRAGMATIST": 0.6,   # Votes ACCEPT if critic_score >= 0.6, else MODIFY
}


def _format_arg(template: str, **kwargs: Any) -> str:
    """Safely format a template string, returning the template on format error."""
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def debater_node(state: AgentState) -> dict[str, Any]:
    """
    LangGraph node: DebaterAgent (Echo Agent Swarm).

    Runs a 2-round structured debate between 3 Echo Agents (Optimist,
    Pessimist, Pragmatist) and determines if there is consensus on the
    ArchitectAgent's proposal.

    Debate output is accumulated in the `debate_transcript` list. Each
    entry is a message dict with keys: { round, stance, content, vote }.

    Args:
        state: Current AgentState.

    Returns:
        Partial state dict:
          - debate_transcript (list of Echo Agent messages)
          - debate_consensus (bool)
          - agent_messages (appended DebaterAgent summary)
    """
    generation  = state["generation"]
    critic_score  = state.get("critic_score", 0.5)
    future_proof  = state.get("futurist_future_proof_score", 0.5)
    fitness       = state.get("fitness_scores", {})
    mutations     = state.get("architect_mutations", [])
    n_total       = max(len(mutations), 1)
    n_accept      = max(1, round(critic_score * n_total))

    template_vars = {
        "accept_count":    n_accept,
        "total_mutations": n_total,
        "future_proof":    future_proof,
        "cost":            fitness.get("costEfficiency", 0.5),
        "aggregate":       fitness.get("aggregate", 0.5),
    }

    transcript: list[dict[str, Any]] = []

    # ── Round 1: Opening arguments ────────────────────────────────────────
    stances = {
        "OPTIMIST":   OPTIMIST_ARGS,
        "PESSIMIST":  PESSIMIST_ARGS,
        "PRAGMATIST": PRAGMATIST_ARGS,
    }

    for stance, templates in stances.items():
        arg_template = random.choice(templates)
        content = _format_arg(arg_template, **template_vars)
        transcript.append({
            "round":   1,
            "stance":  stance,
            "content": content,
            "vote":    None,
        })

    # ── Round 2: Rebuttals ────────────────────────────────────────────────
    round1_summary = (
        f"Optimist argues for adoption; Pessimist raises cost concerns; "
        f"Pragmatist seeks phased approach."
    )

    for stance, templates in stances.items():
        # Pick a different template than Round 1
        rebuttal = random.choice([t for t in templates if t != transcript[list(stances.keys()).index(stance)]["content"]])
        content = _format_arg(rebuttal, **template_vars)
        transcript.append({
            "round":   2,
            "stance":  stance,
            "content": f"Rebuttal to '{round1_summary}': {content}",
            "vote":    None,
        })

    # ── Voting round ──────────────────────────────────────────────────────
    votes: dict[str, str] = {}

    # OPTIMIST: votes ACCEPT if critic_score >= threshold
    votes["OPTIMIST"] = "ACCEPT" if critic_score >= VOTE_THRESHOLDS["OPTIMIST"] else "REJECT"

    # PESSIMIST: high bar for acceptance
    votes["PESSIMIST"] = "ACCEPT" if critic_score >= VOTE_THRESHOLDS["PESSIMIST"] else "REJECT"

    # PRAGMATIST: votes MODIFY most of the time
    if critic_score >= VOTE_THRESHOLDS["PRAGMATIST"]:
        votes["PRAGMATIST"] = "ACCEPT"
    elif critic_score >= 0.4:
        votes["PRAGMATIST"] = "MODIFY"
    else:
        votes["PRAGMATIST"] = "REJECT"

    for entry in transcript:
        if entry["round"] == 2:
            entry["vote"] = votes[entry["stance"]]

    # ── Consensus check ───────────────────────────────────────────────────
    # Treat MODIFY as a soft ACCEPT
    effective_votes = [
        "ACCEPT" if v in ("ACCEPT", "MODIFY") else "REJECT"
        for v in votes.values()
    ]
    n_accept_votes = effective_votes.count("ACCEPT")
    consensus      = n_accept_votes >= 2  # Majority (2 of 3)

    # ── Agent summary message ─────────────────────────────────────────────
    vote_str = ", ".join(f"{s}: {v}" for s, v in votes.items())
    consensus_str = "✅ Consensus reached" if consensus else "⚠️ No consensus"

    summary = (
        f"Echo debate complete (generation {generation}). "
        f"Votes: {vote_str}. {consensus_str}. "
        f"Proposal {'accepted' if consensus else 'contested'} — "
        f"will {'apply' if consensus else 'defer'} architectural mutations."
    )

    msg = {
        "role":       "debater",
        "content":    summary,
        "confidence": round(0.5 + 0.3 * (n_accept_votes / 3), 3),
        "generation": generation,
        "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "debater_verdict",
        generation=generation,
        votes=votes,
        consensus=consensus,
    )

    return {
        "debate_transcript": transcript,
        "debate_consensus":  consensus,
        "agent_messages":    state.get("agent_messages", []) + [msg],
    }
