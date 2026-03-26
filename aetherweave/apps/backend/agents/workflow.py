"""
AetherWeave Backend — LangGraph Multi-Agent Workflow
=====================================================

Wires the four agent nodes into a LangGraph StateGraph that executes
sequentially for each evolutionary generation's debate cycle.

Graph topology
--------------
START → architect → critic → futurist → debater → END

No conditional edges are used in this implementation (all agents always
run). Future versions will add conditional routing:
  - If critic_score < 0.2 → skip futurist and debater, reject proposal.
  - If debate_consensus is False → re-run architect with stricter constraints.

Usage
-----
From EvolutionService (enhanced version):

    from apps.backend.agents.workflow import run_agent_debate

    agent_result = await run_agent_debate(
        genome=individual,
        graph_payload=graph_payload,
        fitness_scores=current_fitness,
        generation=gen_idx,
        intent=intent,
    )
    # agent_result contains all agent_messages and updated fitness_scores
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from apps.backend.agents.state import AgentState
from apps.backend.agents.architect_agent import architect_node
from apps.backend.agents.critic_agent import critic_node
from apps.backend.agents.debater_agent import debater_node
from apps.backend.agents.futurist_agent import futurist_node

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ── LangGraph StateGraph definition ───────────────────────────────────────────

def _build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the multi-agent debate cycle.

    Node execution order: architect → critic → futurist → debater

    Each node receives the full AgentState dict, modifies its slice,
    and returns the updated dict. LangGraph merges the returned fields
    into the existing state automatically (additive merge).

    Returns:
        A compiled LangGraph app ready to be invoked with `.invoke()`.
    """
    graph = StateGraph(AgentState)

    # Register agent nodes
    graph.add_node("architect", architect_node)
    graph.add_node("critic",    critic_node)
    graph.add_node("futurist",  futurist_node)
    graph.add_node("debater",   debater_node)

    # Linear edges: START → architect → critic → futurist → debater → END
    graph.add_edge(START,        "architect")
    graph.add_edge("architect",  "critic")
    graph.add_edge("critic",     "futurist")
    graph.add_edge("futurist",   "debater")
    graph.add_edge("debater",    END)

    return graph.compile()


# Module-level compiled graph (built once, reused for all invocations)
_agent_graph = _build_agent_graph()


# ── Public interface ──────────────────────────────────────────────────────────


async def run_agent_debate(
    genome: list,
    graph_payload: dict[str, Any],
    fitness_scores: dict[str, float],
    generation: int,
    intent: str,
    enable_debate: bool = True,
    config: dict[str, Any] | None = None,
) -> AgentState:
    """
    Run the full agent debate cycle for one evolutionary generation.

    This is the primary entry point called by the enhanced EvolutionService
    at the end of each DEAP generation to let the agents reason about and
    potentially override the fitness scores.

    Flow:
    1. Build initial AgentState from arguments.
    2. Invoke the compiled LangGraph StateGraph synchronously.
       (LangGraph uses asyncio internally for the agent nodes.)
    3. Return the final AgentState after all nodes have run.

    Args:
        genome:        Current DEAP Individual gene list.
        graph_payload: API-formatted graph dict for this individual.
        fitness_scores: Current fitness scores { scalability, cost_efficiency,
                        future_proof, aggregate }.
        generation:    Current DEAP generation index (0-based).
        intent:        Original user intent string.
        enable_debate: If False, skip the debater node (performance mode).
        config:        Optional extra config dict passed to each agent.

    Returns:
        Final AgentState after the full debate cycle. Key fields:
          - fitness_scores      (possibly updated by critic + futurist)
          - agent_messages      (all 4 agent messages)
          - debate_transcript   (Echo Agent debate records)
          - debate_consensus    (bool)
          - architect_mutations (proposed mutations list)
    """
    if not enable_debate:
        # Short-circuit: skip agent debate, return unchanged state
        logger.debug("agent_debate_disabled", generation=generation)
        return AgentState(
            generation=generation,
            individual_genome=genome,
            graph_payload=graph_payload,
            fitness_scores=fitness_scores,
            architect_proposal="",
            architect_mutations=[],
            critic_score=0.0,
            critic_feedback="Debate disabled.",
            futurist_risk_report="",
            futurist_future_proof_score=fitness_scores.get("futureProof", 0.0),
            debate_transcript=[],
            debate_consensus=True,
            agent_messages=[],
            intent=intent,
            config=config or {},
        )

    initial_state = AgentState(
        generation=generation,
        individual_genome=genome,
        graph_payload=graph_payload,
        fitness_scores=dict(fitness_scores),
        architect_proposal="",
        architect_mutations=[],
        critic_score=0.0,
        critic_feedback="",
        futurist_risk_report="",
        futurist_future_proof_score=0.0,
        debate_transcript=[],
        debate_consensus=False,
        agent_messages=[],
        intent=intent,
        config=config or {},
    )

    logger.debug("agent_debate_starting", generation=generation)

    # LangGraph .invoke() is synchronous; wrap in asyncio.to_thread for non-blocking
    import asyncio
    final_state: AgentState = await asyncio.to_thread(
        _agent_graph.invoke, initial_state
    )

    logger.info(
        "agent_debate_complete",
        generation=generation,
        consensus=final_state.get("debate_consensus"),
        n_messages=len(final_state.get("agent_messages", [])),
        updated_aggregate=final_state.get("fitness_scores", {}).get("aggregate"),
    )

    return final_state
