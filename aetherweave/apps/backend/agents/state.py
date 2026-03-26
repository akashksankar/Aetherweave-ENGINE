"""
AetherWeave Backend — LangGraph Multi-Agent State
==================================================

Defines the shared state TypedDict that flows through the LangGraph
StateGraph for each generation's agent debate cycle.

State machine overview
----------------------

┌─────────────────────────────────────────────────────────────┐
│  AgentState flows through nodes in this order:              │
│                                                             │
│  START                                                      │
│    │                                                        │
│    ▼                                                        │
│  ArchitectAgent ──► proposes structural changes             │
│    │                (add/remove/merge nodes)                │
│    ▼                                                        │
│  CriticAgent ──────► scores the proposal via fitness fn     │
│    │                 (returns updated fitness scores)        │
│    ▼                                                        │
│  FuturistAgent ────► Monte-Carlo 2-5yr foresight simulation │
│    │                 (returns risk report + updated score)   │
│    ▼                                                        │
│  DebaterAgent ─────► Echo Agents debate (3 internal stances)│
│    │                 (returns consensus or dissent)          │
│    ▼                                                        │
│  END ──────────────► final AgentState emitted as WS event   │
└─────────────────────────────────────────────────────────────┘

Each node receives the full AgentState, updates its slice, and
returns the updated dict — LangGraph merges it automatically.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """
    Shared state flowing through all LangGraph agent nodes.

    Fields are updated in-place by each agent node. LangGraph
    automatically merges the returned dict with the existing state.

    Attributes
    ----------
    generation : int
        Current DEAP generation index (0-based).
    individual_genome : list
        The DEAP Individual gene list being evaluated this round.
    graph_payload : dict
        The ArchGraph dict derived from `individual_genome`.
    fitness_scores : dict
        Mutable fitness scores updated by each agent:
        { scalability, cost_efficiency, future_proof, aggregate }.
    architect_proposal : str
        Natural-language proposal from the ArchitectAgent.
    architect_mutations : list[dict]
        List of proposed mutation dicts (type, node_idx, rationale).
    critic_score : float
        CriticAgent's aggregate fitness verdict [0, 1].
    critic_feedback : str
        Detailed textual critique from the CriticAgent.
    futurist_risk_report : str
        FuturistAgent's Monte-Carlo risk narrative.
    futurist_future_proof_score : float
        Updated future_proof score after Monte-Carlo simulation [0, 1].
    debate_transcript : list[dict]
        DebaterAgent's internal Echo debate messages (role, content, stance).
    debate_consensus : bool
        True if Echo Agents reached consensus; False if still debating.
    agent_messages : list[dict]
        Accumulates all AgentMessage events emitted during this generation.
    intent : str
        Original user intent string (read-only throughout the graph).
    config : dict
        Freeform config dict (e.g., enable_debate flag, LLM model name).
    """

    generation: int
    individual_genome: list
    graph_payload: dict[str, Any]
    fitness_scores: dict[str, float]

    architect_proposal: str
    architect_mutations: list[dict[str, Any]]

    critic_score: float
    critic_feedback: str

    futurist_risk_report: str
    futurist_future_proof_score: float

    debate_transcript: list[dict[str, Any]]
    debate_consensus: bool

    agent_messages: list[dict[str, Any]]

    intent: str
    config: dict[str, Any]
