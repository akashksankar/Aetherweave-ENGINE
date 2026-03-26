"""
AetherWeave Backend — Enhanced Evolution Service (Part 3)
==========================================================

Extends the base EvolutionService with:

1. NSGA-II multi-objective selection (replaces simple tournament selection).
2. LangGraph agent debate integration — after each DEAP generation, the
   4-agent swarm debates the best individual and potentially overrides
   the fitness scores.
3. Richer WebSocket event payloads that include agent debate transcripts
   so the frontend can render live agent speech bubbles.

NSGA-II overview
----------------
Non-dominated Sorting Genetic Algorithm II (Deb et al., 2002) is the
industry-standard algorithm for multi-objective optimisation. It maintains
a Pareto-optimal front: solutions where no single objective can be improved
without degrading another.

DEAP implementation:
  - `tools.selNSGA2` replaces `tools.selTournament`.
  - The fitness must have mixed weights. We use (+1, +1, +1) to maximise
    all three objectives simultaneously.
  - The Hall-of-Fame stores the 5 individuals on the highest Pareto front.

Integration with agent debate
------------------------------
For each generation G:
  1. DEAP runs `algorithms.varAnd()` → offspring.
  2. Fitness is evaluated for all invalid individuals.
  3. NSGA-II selection produces the next population.
  4. The best individual's fitness is passed to `run_agent_debate()`.
  5. If the agents update the fitness scores (critic + futurist override),
     we update the best individual's fitness values to match.
  6. A `WSGenerationEvent` is emitted with the full agent debate payload.

WebSocket event shape (generation type):
  {
    "type": "generation",
    "generation": 5,
    "graph": { ... ArchGraph ... },
    "fitness": { scalability, costEfficiency, futureProof, aggregate },
    "agentDebate": {
      "messages": [ { role, content, confidence, generation, timestamp }, ... ],
      "transcript": [ { round, stance, content, vote }, ... ],
      "consensus": bool,
      "criticScore": float,
      "futuristScore": float,
    }
  }
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog
from deap import algorithms, creator, tools

from apps.backend.core.config import settings
from apps.backend.services.evolution_service import (
    EvolutionService,
    individual_to_nx,
    nx_to_api_payload,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class EnhancedEvolutionService(EvolutionService):
    """
    NSGA-II powered evolution service with integrated multi-agent debate.

    Inherits all DEAP gene/individual/crossover/mutate logic from
    `EvolutionService` and overrides:
      - `_build_toolbox()` to use `selNSGA2` instead of `selTournament`.
      - `run_evolution()` to include agent debate per generation.

    All docstring annotations from the parent class remain valid.
    """

    def __init__(self) -> None:
        super().__init__()
        # Override the selection operator with NSGA-II
        self._toolbox.unregister("select")
        self._toolbox.register("select", tools.selNSGA2)
        logger.info("nsga2_selection_enabled")

    async def run_evolution(  # type: ignore[override]
        self,
        intent: str,
        architecture_id: str,
        generations: int,
        population_size: int,
        seed: int | None = None,
        enable_debate: bool = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        NSGA-II evolution loop with per-generation agent debate.

        Overrides the base `run_evolution()` async generator to:
        1. Use NSGA-II selection (Pareto-front based).
        2. Run `run_agent_debate()` after each generation.
        3. Emit richer WebSocket events including the full `agentDebate` payload.

        Args:
            intent:           User's architectural intent string.
            architecture_id:  UUID string for tracking.
            generations:      Number of DEAP generations to run.
            population_size:  Number of individuals in the population.
            seed:             Optional RNG seed.
            enable_debate:    Whether to run the LangGraph debate per generation.

        Yields:
            Dict events matching WSEventPayload union from types.ts:
              - { type: "generation", ... } per generation
              - { type: "complete",   ... } at the end
        """
        # Import here to avoid circular import at module load time
        from apps.backend.agents.workflow import run_agent_debate

        t_start = time.monotonic()
        population = self.initialize_population(
            size=population_size, intent=intent, seed=seed
        )

        hof           = tools.HallOfFame(maxsize=5)
        fitness_history: list[float] = []
        all_agent_events: list[dict[str, Any]] = []

        # ── Evaluate initial population ───────────────────────────────────
        fitnesses = list(map(self._toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit
        hof.update(population)

        logger.info(
            "nsga2_evolution_started",
            architecture_id=architecture_id,
            generations=generations,
            population_size=population_size,
        )

        for gen_idx in range(generations):
            # ── NSGA-II variation and selection ───────────────────────────
            offspring = algorithms.varAnd(
                population, self._toolbox, cxpb=0.7, mutpb=0.3
            )

            invalid = [ind for ind in offspring if not ind.fitness.valid]
            for ind, fit in zip(invalid, map(self._toolbox.evaluate, invalid)):
                ind.fitness.values = fit

            # NSGA-II selNSGA2 requires the combined population for proper Pareto ranking
            combined = population + offspring
            population = self._toolbox.select(combined, k=population_size)
            hof.update(population)

            # ── Best individual this generation ───────────────────────────
            best = hof[0]
            s, c, f = best.fitness.values
            raw_aggregate = round(0.4 * s + 0.3 * c + 0.3 * f, 4)

            fitness_payload = {
                "scalability":    round(s, 4),
                "costEfficiency": round(c, 4),
                "futureProof":    round(f, 4),
                "aggregate":      raw_aggregate,
            }

            G = individual_to_nx(list(best))
            graph_payload = nx_to_api_payload(
                G, architecture_id, intent[:80] or "Unnamed",
                fitness_payload, gen_idx
            )

            # ── Agent debate (every N generations or if enabled) ──────────
            agent_debate_payload: dict[str, Any] | None = None

            # Run debate every 3 generations and on the last generation
            should_debate = enable_debate and (
                gen_idx % 3 == 0 or gen_idx == generations - 1
            )

            if should_debate:
                try:
                    agent_state = await run_agent_debate(
                        genome=list(best),
                        graph_payload=graph_payload,
                        fitness_scores=dict(fitness_payload),
                        generation=gen_idx,
                        intent=intent,
                        enable_debate=enable_debate,
                    )

                    # Override fitness with agent-updated scores
                    updated = agent_state.get("fitness_scores", {})
                    if updated.get("aggregate", 0) > raw_aggregate:
                        fitness_payload = {
                            "scalability":    updated.get("scalability", s),
                            "costEfficiency": updated.get("costEfficiency", c),
                            "futureProof":    updated.get("futureProof", f),
                            "aggregate":      updated.get("aggregate", raw_aggregate),
                        }
                        # Update best individual's fitness in DEAP
                        best.fitness.values = (
                            fitness_payload["scalability"],
                            fitness_payload["costEfficiency"],
                            fitness_payload["futureProof"],
                        )

                    agent_debate_payload = {
                        "messages":      agent_state.get("agent_messages", []),
                        "transcript":    agent_state.get("debate_transcript", []),
                        "consensus":     agent_state.get("debate_consensus", False),
                        "criticScore":   agent_state.get("critic_score", 0.0),
                        "futuristScore": agent_state.get("futurist_future_proof_score", 0.0),
                        "proposal":      agent_state.get("architect_proposal", ""),
                    }
                    all_agent_events.append(agent_debate_payload)

                except Exception as e:
                    logger.warning("agent_debate_failed", generation=gen_idx, error=str(e))
                    agent_debate_payload = None

            fitness_history.append(fitness_payload["aggregate"])

            # ── Emit generation event ─────────────────────────────────────
            yield {
                "type":        "generation",
                "generation":  gen_idx,
                "graph":       graph_payload,
                "fitness":     fitness_payload,
                "agentDebate": agent_debate_payload,
            }

            await asyncio.sleep(0)  # yield control to event loop

        # ── Emit completion event ─────────────────────────────────────────
        duration_ms = round((time.monotonic() - t_start) * 1000, 2)
        best = hof[0]
        s, c, f = best.fitness.values
        agg = round(0.4 * s + 0.3 * c + 0.3 * f, 4)
        best_fitness = {
            "scalability":    round(s, 4),
            "costEfficiency": round(c, 4),
            "futureProof":    round(f, 4),
            "aggregate":      agg,
        }
        best_G = individual_to_nx(list(best))
        best_graph = nx_to_api_payload(
            best_G, architecture_id, intent[:80] or "Unnamed",
            best_fitness, generations
        )

        logger.info(
            "nsga2_evolution_complete",
            architecture_id=architecture_id,
            duration_ms=duration_ms,
            best_fitness=agg,
        )

        yield {
            "type": "complete",
            "result": {
                "bestGraph":      best_graph,
                "mutations":      [],
                "fitnessHistory": fitness_history,
                "durationMs":     duration_ms,
                "generationsRun": generations,
                "agentDebate":    all_agent_events,
            },
        }


# ── Module-level singleton (replaces the base EvolutionService singleton) ─────
enhanced_evolution_service = EnhancedEvolutionService()
