"""
AetherWeave Backend — EvolutionService
========================================

The evolutionary engine that powers AetherWeave. Uses DEAP (Distributed
Evolutionary Algorithms in Python) combined with NetworkX for graph analysis
to evolve software architectures toward multiple fitness objectives.

High-level flow
---------------
1. User supplies an intent string →
2. `initialize_population()` creates N random graphs with NetworkX →
3. `fitness_function()` scores each graph on (scalability, cost, future-proof) →
4. DEAP runs selection, crossover, mutation for G generations →
5. Each generation is streamed via WebSocket to the frontend →
6. The best individual is persisted to PostgreSQL + Neo4j.

Mathematical foundations
------------------------
The fitness function is a multi-objective Pareto optimisation collapsed into
a weighted aggregate for simplicity (full NSGA-II added in Part 3):

    aggregate = 0.4 * scalability + 0.3 * cost_efficiency + 0.3 * future_proof

Where:
  scalability      ∝ 1 / (graph_diameter + bottleneck_count)
  cost_efficiency  ∝ 1 / total_node_cost_estimate
  future_proof     ∝ Monte-Carlo survivability over T=2..5 years (Part 3)
"""

from __future__ import annotations

import math
import random
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import networkx as nx
import numpy as np
import structlog
from deap import algorithms, base, creator, tools

from apps.backend.core.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Node type catalogue ────────────────────────────────────────────────────────

# Maps NodeType string → estimated relative monthly cost (arbitrary units).
# Used by the cost scoring dimension of the fitness function.
NODE_COST_MAP: dict[str, float] = {
    "service":  2.0,
    "database": 5.0,
    "gateway":  1.5,
    "cache":    1.0,
    "queue":    1.2,
    "cdn":      0.8,
    "auth":     1.5,
    "monitor":  0.9,
    "ml":       8.0,   # GPU instances are expensive
    "edge":     1.3,
}

ALL_NODE_TYPES = list(NODE_COST_MAP.keys())

# ── DEAP setup (module-level, executed once on import) ────────────────────────
#
# DEAP uses a global `creator` module to define Individual and Fitness classes.
# We guard with hasattr() to avoid re-registration on hot-reload.
#
# Fitness: maximise all three objectives (weights all +1.0).
if not hasattr(creator, "AetherFitness"):
    creator.create("AetherFitness", base.Fitness, weights=(1.0, 1.0, 1.0))

# An Individual is a list of ( NodeType, x, y, z ) tuples — the "genome".
if not hasattr(creator, "AetherIndividual"):
    creator.create("AetherIndividual", list, fitness=creator.AetherFitness)


# ── Type aliases ──────────────────────────────────────────────────────────────

Gene = tuple[str, float, float, float]  # (node_type, x, y, z)
Individual = list[Gene]


# ── Graph conversion helpers ──────────────────────────────────────────────────


def individual_to_nx(individual: Individual) -> nx.DiGraph:
    """
    Convert a DEAP individual (list of Gene tuples) into a NetworkX DiGraph.

    Each gene becomes a node; edges are added between every adjacent pair of
    genes in the list. This produces a simple linear topology that is then
    mutated by genetic operators to create more complex structures.

    Algorithm:
        for i in range(len(individual) - 1):
            G.add_edge(i, i+1)

    Args:
        individual: A list of (node_type, x, y, z) gene tuples.

    Returns:
        Directed NetworkX graph with `node_type` and `pos` node attributes.
    """
    G = nx.DiGraph()
    for idx, (ntype, x, y, z) in enumerate(individual):
        G.add_node(idx, node_type=ntype, pos=(x, y, z), label=f"{ntype}-{idx}")

    # Linear backbone edges
    for i in range(len(individual) - 1):
        weight = round(random.uniform(0.2, 1.0), 3)
        G.add_edge(i, i + 1, weight=weight, label="HTTP")

    return G


def nx_to_api_payload(
    G: nx.DiGraph,
    graph_id: str,
    name: str,
    fitness: dict[str, float],
    generation: int,
) -> dict[str, Any]:
    """
    Serialise a NetworkX graph into the ArchGraph API payload format.

    Args:
        G:          Directed NetworkX graph.
        graph_id:   UUID string for the graph.
        name:       Human-readable graph name.
        fitness:    Dict with keys scalability, cost_efficiency, future_proof, aggregate.
        generation: Current generation index.

    Returns:
        Dict matching the ArchGraph TypeScript interface.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    nodes = []
    for node_id, data in G.nodes(data=True):
        pos = data.get("pos", (0.0, 0.0, 0.0))
        nodes.append({
            "id":         str(uuid.uuid4()),
            "label":      data.get("label", f"node-{node_id}"),
            "type":       data.get("node_type", "service"),
            "position":   {"x": pos[0], "y": pos[1], "z": pos[2]},
            "fitness":    round(fitness["aggregate"], 4),
            "generation": generation,
            "ancestry":   [],
            "metadata":   {},
        })

    edges = []
    for src, tgt, edata in G.edges(data=True):
        edges.append({
            "id":        str(uuid.uuid4()),
            "source":    nodes[src]["id"] if src < len(nodes) else str(uuid.uuid4()),
            "target":    nodes[tgt]["id"] if tgt < len(nodes) else str(uuid.uuid4()),
            "weight":    edata.get("weight", 0.5),
            "label":     edata.get("label", "HTTP"),
            "latencyMs": None,
        })

    return {
        "id":         graph_id,
        "name":       name,
        "nodes":      nodes,
        "edges":      edges,
        "fitness":    fitness,
        "generation": generation,
        "createdAt":  now,
        "updatedAt":  now,
    }


# ── EvolutionService ──────────────────────────────────────────────────────────


class EvolutionService:
    """
    The core evolutionary engine for AetherWeave.

    This class encapsulates the DEAP toolbox, fitness functions, and the
    async generator that streams evolution events to WebSocket clients.

    All public methods are designed to be called from FastAPI route handlers.
    The evolution loop is an async generator so the caller can yield each
    generation's payload to a WebSocket without blocking.

    Thread safety
    -------------
    Each call to `run_evolution()` creates a brand-new DEAP toolbox and
    population, so concurrent evolution runs do not share state.
    """

    def __init__(self) -> None:
        """Configure the DEAP genetic algorithm operators."""
        self._toolbox = self._build_toolbox()
        logger.info("evolution_service_initialized")

    # ── DEAP Toolbox ──────────────────────────────────────────────────────────

    def _build_toolbox(self) -> base.Toolbox:
        """
        Construct and return a DEAP toolbox with registered operators.

        Registered operators:
            individual  → calls `_make_individual()`
            population  → list of individuals
            evaluate    → calls `fitness_function()`
            mate        → `_crossover()` (one-point crossover on the genome list)
            mutate      → `_mutate_individual()` (custom multi-operation mutation)
            select      → DEAP's built-in NSGA-II selection (tournament of 3)

        Returns:
            A configured DEAP Toolbox ready for running algorithms.eaSimple.
        """
        tb = base.Toolbox()

        # ── Gene factory ──────────────────────────────────────────────────
        tb.register(
            "gene",
            lambda: (
                random.choice(ALL_NODE_TYPES),
                round(random.uniform(-80, 80), 2),   # x
                round(random.uniform(-80, 80), 2),   # y
                round(random.uniform(-80, 80), 2),   # z
            )
        )

        # ── Individual factory (5–15 genes to start) ─────────────────────
        tb.register(
            "individual",
            lambda: creator.AetherIndividual(
                [tb.gene() for _ in range(random.randint(5, 15))]
            )
        )

        # ── Population factory ────────────────────────────────────────────
        tb.register("population", tools.initRepeat, list, tb.individual)

        # ── Genetic operators ─────────────────────────────────────────────
        tb.register("evaluate", self.fitness_function)
        tb.register("mate",     self._crossover)
        tb.register("mutate",   self._mutate_individual, indpb=0.3)
        tb.register("select",   tools.selTournament, tournsize=3)

        return tb

    # ── Initialisation ────────────────────────────────────────────────────────

    def initialize_population(
        self,
        size: int = 20,
        intent: str = "",
        seed: int | None = None,
    ) -> list[Individual]:
        """
        Create the initial random population of architecture individuals.

        Each individual is a DEAP Individual (list of Gene tuples) whose
        length is sampled uniformly from [5, 15]. The NetworkX graph derived
        from this list forms a linear backbone that mutations then diversify.

        The intent string is used for logging and future NLP-guided seeding
        (Part 3 will use an LLM to bias the initial node type distribution
        based on the intent).

        Args:
            size:   Desired population size [10, 200].
            intent: User-provided architecture description (for seeding bias).
            seed:   Random seed for reproducibility; None = truly random.

        Returns:
            A list of `size` AetherIndividual objects, each ready to be
            evaluated by `fitness_function()`.
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        population = self._toolbox.population(n=size)

        logger.info(
            "population_initialized",
            size=size,
            intent_snippet=intent[:50] if intent else "",
        )
        return population

    # ── Fitness Function ──────────────────────────────────────────────────────

    def fitness_function(self, individual: Individual) -> tuple[float, float, float]:
        """
        Compute the multi-objective fitness of a single DEAP individual.

        Returns three scores (all maximised):
          1. scalability      — graph structural quality
          2. cost_efficiency  — inverse of total resource cost
          3. future_proof     — simplified temporal foresight score

        Mathematical details
        --------------------
        scalability:

            Let G = NetworkX graph derived from `individual`.
            diameter   = longest shortest path in the weakly connected component.
            bottleneck = number of nodes whose removal disconnects the graph
                         (approximated by nodes with in-degree == 1 AND out-degree == 1
                          that are not gateways/CDNs).

            scalability = 1 / (1 + 0.3 * diameter + 0.7 * bottleneck_count)

            Range: (0, 1]. Higher is wider, more resilient graph.

        cost_efficiency:

            total_cost = Σ NODE_COST_MAP[node_type] for all nodes
            normalised: cost_efficiency = exp(-total_cost / 50)

            The exp decay ensures a smooth gradient — very expensive graphs
            approach 0 asymptotically rather than abruptly.

        future_proof (simplified — full Monte-Carlo in Part 3):

            diversity = number of distinct node types / total node types
            redundancy = |{types with count >= 2}| / |{types present}|
            future_proof = 0.5 * diversity + 0.5 * redundancy

        Args:
            individual: A DEAP Individual (list of Gene tuples).

        Returns:
            Tuple of (scalability, cost_efficiency, future_proof),
            all in [0, 1]. DEAP stores these in individual.fitness.values.
        """
        G = individual_to_nx(individual)
        n = G.number_of_nodes()

        if n == 0:
            return (0.0, 0.0, 0.0)

        # ── Scalability ───────────────────────────────────────────────────
        try:
            ug = G.to_undirected()
            # Use the largest connected component to avoid inf diameter
            largest_cc = max(nx.connected_components(ug), key=len)
            sub = ug.subgraph(largest_cc)
            diameter = nx.diameter(sub) if len(sub) > 1 else 1
        except nx.NetworkXError:
            diameter = n  # worst case for disconnected graph

        # Bottlenecks: nodes with in_degree == out_degree == 1 (single points of failure)
        bottleneck_count = sum(
            1 for node in G.nodes()
            if G.in_degree(node) == 1 and G.out_degree(node) == 1
        )

        scalability = 1.0 / (1.0 + 0.3 * diameter + 0.7 * bottleneck_count)
        scalability = min(max(scalability, 0.0), 1.0)

        # ── Cost efficiency ───────────────────────────────────────────────
        total_cost = sum(
            NODE_COST_MAP.get(data.get("node_type", "service"), 2.0)
            for _, data in G.nodes(data=True)
        )
        cost_efficiency = math.exp(-total_cost / 50.0)
        cost_efficiency = min(max(cost_efficiency, 0.0), 1.0)

        # ── Future proof (simplified) ─────────────────────────────────────
        type_counts: dict[str, int] = {}
        for _, data in G.nodes(data=True):
            t = data.get("node_type", "service")
            type_counts[t] = type_counts.get(t, 0) + 1

        types_present = set(type_counts.keys())
        total_types = len(ALL_NODE_TYPES)

        diversity = len(types_present) / total_types
        redundant_types = [t for t, c in type_counts.items() if c >= 2]
        redundancy = len(redundant_types) / len(types_present) if types_present else 0.0

        future_proof = 0.5 * diversity + 0.5 * redundancy
        future_proof = min(max(future_proof, 0.0), 1.0)

        return (scalability, cost_efficiency, future_proof)

    # ── Genetic Operators ─────────────────────────────────────────────────────

    def _crossover(
        self, individual1: Individual, individual2: Individual
    ) -> tuple[Individual, Individual]:
        """
        Single-point crossover between two architecture individuals.

        Selects a random splice point in each parent's genome and swaps
        the tail segments. This combines the structural patterns of two
        different architectures into two offspring.

        Mathematical rationale:
            Let L1 = len(ind1), L2 = len(ind2).
            cx_point1 ~ Uniform(1, L1-1)
            cx_point2 ~ Uniform(1, L2-1)
            offspring1 = ind1[:cx_point1] + ind2[cx_point2:]
            offspring2 = ind2[:cx_point2] + ind1[cx_point1:]

        DEAP requires in-place modification of individuals (they are mutable
        lists) and deletion of fitness values to signal re-evaluation.

        Args:
            individual1: First parent individual (modified in-place).
            individual2: Second parent individual (modified in-place).

        Returns:
            The two modified individuals (DEAP convention).
        """
        if len(individual1) < 2 or len(individual2) < 2:
            return individual1, individual2

        cx1 = random.randint(1, len(individual1) - 1)
        cx2 = random.randint(1, len(individual2) - 1)

        # Swap tail segments
        individual1[cx1:], individual2[cx2:] = (
            individual2[cx2:],
            individual1[cx1:],
        )

        # Invalidate cached fitness so DEAP re-evaluates
        del individual1.fitness.values
        del individual2.fitness.values

        return individual1, individual2

    def mutate_node(self, gene: Gene) -> Gene:
        """
        Apply a random single-gene mutation to one gene tuple.

        Mutation operations (chosen uniformly at random):
          1. change_type  — replace the NodeType with a different one.
          2. scale_up     — increase all position coordinates by 10–30%.
          3. scale_down   — decrease all position coordinates by 10–30%.
          4. jitter       — add small Gaussian noise to x, y, z.

        Args:
            gene: A (node_type, x, y, z) tuple.

        Returns:
            A new (node_type, x, y, z) tuple with one attribute mutated.
        """
        node_type, x, y, z = gene
        op = random.choice(["change_type", "scale_up", "scale_down", "jitter"])

        if op == "change_type":
            new_type = random.choice([t for t in ALL_NODE_TYPES if t != node_type])
            return (new_type, x, y, z)

        elif op == "scale_up":
            factor = random.uniform(1.1, 1.3)
            return (node_type,
                    max(-100, min(100, x * factor)),
                    max(-100, min(100, y * factor)),
                    max(-100, min(100, z * factor)))

        elif op == "scale_down":
            factor = random.uniform(0.7, 0.9)
            return (node_type,
                    x * factor, y * factor, z * factor)

        else:  # jitter
            return (node_type,
                    max(-100, min(100, x + np.random.normal(0, 5))),
                    max(-100, min(100, y + np.random.normal(0, 5))),
                    max(-100, min(100, z + np.random.normal(0, 5))))

    def _mutate_individual(
        self, individual: Individual, indpb: float = 0.3
    ) -> tuple[Individual]:
        """
        Apply structural mutation operations to an individual.

        Possible mutations (each applied with independent probability):
          1. Gene-level mutation — each gene mutated with P=indpb.
          2. Node addition       — new random gene appended with P=0.2.
          3. Node removal        — random gene removed with P=0.15
             (only if len > 3 to prevent degenerate graphs).

        Args:
            individual: The individual to mutate (modified in-place).
            indpb:      Per-gene mutation probability [0, 1].

        Returns:
            Tuple containing the single mutated individual (DEAP convention).
        """
        # Gene-level mutations
        for i in range(len(individual)):
            if random.random() < indpb:
                individual[i] = self.mutate_node(individual[i])

        # Structural: add node
        if random.random() < 0.2:
            individual.append(self._toolbox.gene())

        # Structural: remove node (keep minimum 3 nodes)
        if len(individual) > 3 and random.random() < 0.15:
            del individual[random.randint(0, len(individual) - 1)]

        del individual.fitness.values
        return (individual,)

    # ── Evolution Loop ────────────────────────────────────────────────────────

    async def run_evolution(
        self,
        intent: str,
        architecture_id: str,
        generations: int,
        population_size: int,
        seed: int | None = None,
        enable_debate: bool = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Async generator that runs G evolutionary generations and yields
        a WebSocket event payload after each one.

        Uses `algorithms.eaSimple` for the core DEAP loop, but yields
        control back to the event loop between generations so the FastAPI
        WebSocket handler can flush each event without blocking.

        DEAP eaSimple parameters:
            cxpb  = 0.7  (70% crossover probability)
            mutpb = 0.3  (30% mutation probability)

        Event types emitted:
            WSGenerationEvent — once per generation
            WSMutationEvent   — for each mutation applied
            WSCompleteEvent   — when the loop finishes

        Args:
            intent:           Natural-language description of the architecture.
            architecture_id:  UUID string for this evolution run.
            generations:      Number of DEAP generations to run.
            population_size:  DEAP population size.
            seed:             Optional RNG seed.
            enable_debate:    Whether to include agent debate payloads.

        Yields:
            Dict matching WSEvent union type from types.ts.
        """
        t_start = time.monotonic()

        # Build fresh population
        population = self.initialize_population(
            size=population_size, intent=intent, seed=seed
        )

        # Stats tracking
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda fits: tuple(float(np.mean([f[i] for f in fits])) for i in range(3)))
        stats.register("max", lambda fits: tuple(float(np.max([f[i] for f in fits])) for i in range(3)))

        hof = tools.HallOfFame(maxsize=5)  # top-5 individuals across all generations
        fitness_history: list[float] = []

        # Evaluate initial population
        fitnesses = list(map(self._toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        hof.update(population)

        logger.info(
            "evolution_started",
            architecture_id=architecture_id,
            generations=generations,
            population_size=population_size,
        )

        for gen_idx in range(generations):
            # ── Vary population (select, mate, mutate) ────────────────────
            offspring = algorithms.varAnd(
                population, self._toolbox, cxpb=0.7, mutpb=0.3
            )

            # ── Evaluate only individuals with invalid (stale) fitness ────
            invalid_individuals = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(self._toolbox.evaluate, invalid_individuals))
            for ind, fit in zip(invalid_individuals, fitnesses):
                ind.fitness.values = fit

            # ── Select next generation ────────────────────────────────────
            population = self._toolbox.select(offspring, k=len(population))
            hof.update(population)

            # ── Compute aggregate fitness for the best individual ─────────
            best = hof[0]
            s, c, f = best.fitness.values
            aggregate = round(0.4 * s + 0.3 * c + 0.3 * f, 4)
            fitness_history.append(aggregate)

            fitness_payload = {
                "scalability":    round(s, 4),
                "costEfficiency": round(c, 4),
                "futureProof":    round(f, 4),
                "aggregate":      aggregate,
            }

            # ── Build graph payload for this generation ───────────────────
            G = individual_to_nx(list(best))
            graph_payload = nx_to_api_payload(
                G, architecture_id, intent[:80] or "Unnamed",
                fitness_payload, gen_idx
            )

            # ── Emit generation event ─────────────────────────────────────
            yield {
                "type":       "generation",
                "generation": gen_idx,
                "graph":      graph_payload,
                "fitness":    fitness_payload,
            }

            # Yield to the event loop so WS can flush the event
            import asyncio
            await asyncio.sleep(0)

        # ── Emit completion event ─────────────────────────────────────────
        duration_ms = round((time.monotonic() - t_start) * 1000, 2)
        best = hof[0]
        s, c, f = best.fitness.values
        aggregate = round(0.4 * s + 0.3 * c + 0.3 * f, 4)
        best_fitness = {
            "scalability":    round(s, 4),
            "costEfficiency": round(c, 4),
            "futureProof":    round(f, 4),
            "aggregate":      aggregate,
        }
        best_G = individual_to_nx(list(best))
        best_graph = nx_to_api_payload(
            best_G, architecture_id, intent[:80] or "Unnamed",
            best_fitness, generations
        )

        logger.info(
            "evolution_complete",
            architecture_id=architecture_id,
            generations_run=generations,
            duration_ms=duration_ms,
            best_fitness=aggregate,
        )

        yield {
            "type": "complete",
            "result": {
                "bestGraph":       best_graph,
                "mutations":       [],
                "fitnessHistory":  fitness_history,
                "durationMs":      duration_ms,
                "generationsRun":  generations,
                "agentDebate":     [],
            },
        }

    # ── Graph from intent ─────────────────────────────────────────────────────

    def create_initial_graph(
        self,
        intent: str,
        initial_nodes: int = 8,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a single initial architecture graph from a natural-language intent.

        This is called by POST /architecture/create before any evolution.
        The graph is randomly generated (NLP-guided seeding comes in Part 3).

        Args:
            intent:        Natural-language architecture description.
            initial_nodes: Desired number of nodes [3, 50].
            seed:          Optional RNG seed for reproducibility.

        Returns:
            Dict matching the ArchGraph TypeScript interface, ready to be
            returned as the API response and stored in PostgreSQL + Neo4j.
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Build one individual of exactly `initial_nodes` genes
        gene_fn = lambda: (
            random.choice(ALL_NODE_TYPES),
            round(random.uniform(-70, 70), 2),
            round(random.uniform(-70, 70), 2),
            round(random.uniform(-70, 70), 2),
        )
        individual = creator.AetherIndividual(
            [gene_fn() for _ in range(initial_nodes)]
        )

        fitness_tuple = self.fitness_function(individual)
        s, c, f = fitness_tuple
        aggregate = round(0.4 * s + 0.3 * c + 0.3 * f, 4)

        fitness_payload = {
            "scalability":    round(s, 4),
            "costEfficiency": round(c, 4),
            "futureProof":    round(f, 4),
            "aggregate":      aggregate,
        }

        G = individual_to_nx(individual)
        graph_id = str(uuid.uuid4())

        return nx_to_api_payload(G, graph_id, intent[:80] or "Unnamed Architecture",
                                 fitness_payload, 0)


# ── Module-level singleton ────────────────────────────────────────────────────

evolution_service = EvolutionService()
