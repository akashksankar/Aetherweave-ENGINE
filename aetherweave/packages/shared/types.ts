/**
 * @fileoverview AetherWeave Shared TypeScript Types
 * 
 * These types are shared between the frontend and backend (mirrored in types.py).
 * Every interface field is documented with its purpose and valid range.
 * 
 * @module @aetherweave/shared/types
 */

// ─── Node Types ──────────────────────────────────────────────────────────────

/**
 * Represents the type of architectural node in the loom.
 * Maps directly to Neo4j node labels and DEAP individual gene positions.
 */
export type NodeType =
  | "service"       // Microservice / standalone compute unit
  | "database"      // Any persistent storage system
  | "gateway"       // API gateway / reverse proxy
  | "cache"         // In-memory cache layer
  | "queue"         // Message queue / event stream
  | "cdn"           // Content delivery network
  | "auth"          // Authentication / authorisation service
  | "monitor"       // Observability / alerting node
  | "ml"            // Machine-learning inference node
  | "edge";         // Edge compute node (CDN-adjacent logic)

/**
 * Mutation operations that can be applied to a node during evolution.
 * Mirrors the DEAP genetic operator set in Python.
 */
export type MutationType =
  | "add_node"      // Introduce a brand-new node to the graph
  | "remove_node"   // Prune a node from the graph
  | "merge_nodes"   // Collapse two compatible nodes into one
  | "split_node"    // Divide one overloaded node into two
  | "change_type"   // Reclassify a node's role
  | "add_edge"      // Create a dependency between two nodes
  | "remove_edge"   // Remove an existing dependency
  | "scale_up"      // Increase node resource allocation
  | "scale_down";   // Decrease node resource allocation

// ─── Core Entities ───────────────────────────────────────────────────────────

/**
 * A single node in the 3D architecture loom.
 * Position is in world-space units; fitness is a 0-1 normalised score.
 */
export interface ArchNode {
  /** Unique identifier (UUID v4) */
  id: string;
  /** Human-readable label rendered above the 3D sphere */
  label: string;
  /** Semantic role of this node */
  type: NodeType;
  /**
   * 3D world-space position.
   * x, y, z are all in the range [-100, 100] for the default scene.
   */
  position: { x: number; y: number; z: number };
  /**
   * Normalised fitness score [0, 1].
   * Higher = better overall architecture contribution.
   */
  fitness: number;
  /**
   * Generation index in which this node first appeared.
   * Used for lineage tracking in the mutation history panel.
   */
  generation: number;
  /**
   * Ancestry chain: IDs of all predecessor nodes (oldest first).
   * Enables the loom to draw lineage tubes in the 3D canvas.
   */
  ancestry: string[];
  /** Freeform metadata attached by the architect agent */
  metadata: Record<string, unknown>;
}

/**
 * A directed edge between two ArchNodes.
 * Rendered as a glowing mycelium tube in 3D space.
 */
export interface ArchEdge {
  /** Unique edge identifier */
  id: string;
  /** Source node ID */
  source: string;
  /** Target node ID */
  target: string;
  /**
   * Edge weight [0, 1] — represents traffic / coupling strength.
   * Affects tube thickness in the 3D renderer.
   */
  weight: number;
  /** Edge label (e.g., "HTTP", "gRPC", "AMQP") */
  label: string;
  /** Optional latency estimate in milliseconds */
  latencyMs?: number;
}

/**
 * A full architectural graph — the primary data structure of AetherWeave.
 */
export interface ArchGraph {
  /** Graph identifier (matches UUID in Neo4j) */
  id: string;
  /** Display name chosen by the user */
  name: string;
  /** All nodes in this architecture */
  nodes: ArchNode[];
  /** All directed edges between nodes */
  edges: ArchEdge[];
  /** Overall fitness aggregate across dimensions */
  fitness: FitnessScore;
  /** Current evolution generation counter */
  generation: number;
  /** ISO-8601 creation timestamp */
  createdAt: string;
  /** ISO-8601 last-updated timestamp */
  updatedAt: string;
}

// ─── Fitness & Evolution ─────────────────────────────────────────────────────

/**
 * Multi-objective fitness score for a given architecture.
 * Each dimension is independently optimised by the evolutionary engine.
 */
export interface FitnessScore {
  /**
   * Scalability score [0, 1].
   * Derived from graph diameter, fan-out ratios, and bottleneck detection.
   */
  scalability: number;
  /**
   * Estimated monthly infrastructure cost index [0, 1] (inverted — lower cost = higher score).
   * Normalised against a reference architecture.
   */
  costEfficiency: number;
  /**
   * Future-proof score [0, 1].
   * Predicted by the FuturistAgent using Monte-Carlo simulation over 2-5 years.
   */
  futureProof: number;
  /**
   * Aggregate score — weighted mean: 0.4*scalability + 0.3*costEfficiency + 0.3*futureProof
   */
  aggregate: number;
}

/**
 * A single mutation event recorded in the evolution history.
 */
export interface Mutation {
  /** Unique mutation identifier */
  id: string;
  /** Generation in which this mutation occurred */
  generation: number;
  /** Type of genetic operation applied */
  type: MutationType;
  /** ID of the primary node affected */
  nodeId: string;
  /** Optional second node ID (for merge / crossover operations) */
  partnerNodeId?: string;
  /** Fitness delta introduced by this mutation (can be negative) */
  fitnessDelta: number;
  /** ISO-8601 timestamp */
  timestamp: string;
  /** Human-readable explanation from the ArchitectAgent */
  rationale: string;
}

/**
 * Complete result object returned after running N evolutionary generations.
 */
export interface EvolutionResult {
  /** The best architecture found across all generations */
  bestGraph: ArchGraph;
  /** All mutation events, ordered chronologically */
  mutations: Mutation[];
  /** Fitness progression: index = generation, value = aggregate fitness */
  fitnessHistory: number[];
  /** Total wall-clock time taken in milliseconds */
  durationMs: number;
  /** Number of generations actually executed (may be < requested if converged early) */
  generationsRun: number;
  /** Agent debate transcript for the final generation */
  agentDebate: AgentMessage[];
}

// ─── Symbiosis / DNA Sharing ─────────────────────────────────────────────────

/**
 * A symbiosis token — secure UUID-based handle for sharing a sub-graph
 * with another AetherWeave user without exposing the raw graph data.
 */
export interface SymbiosisToken {
  /** The share token (opaque UUID, not the graph ID) */
  token: string;
  /** ID of the graph being shared */
  graphId: string;
  /** Which node IDs are included in this share (partial graph exports) */
  sharedNodeIds: string[];
  /** ISO-8601 expiry time */
  expiresAt: string;
  /** Optional password hash for protected sharing */
  passwordHash?: string;
}

// ─── Multi-Agent Types ───────────────────────────────────────────────────────

/**
 * Agent role in the LangGraph swarm.
 */
export type AgentRole = "architect" | "critic" | "futurist" | "debater";

/**
 * A single message from an LLM agent in the debate cycle.
 */
export interface AgentMessage {
  /** Which agent produced this message */
  role: AgentRole;
  /** Message content (markdown allowed) */
  content: string;
  /** Confidence score the agent assigns to this message [0, 1] */
  confidence: number;
  /** Generation index when this message was produced */
  generation: number;
  /** ISO-8601 timestamp */
  timestamp: string;
}

// ─── WebSocket Event Types ───────────────────────────────────────────────────

/**
 * Discriminated union of all WebSocket event types emitted by the backend.
 */
export type WSEvent =
  | WSGenerationEvent
  | WSMutationEvent
  | WSAgentEvent
  | WSCompleteEvent
  | WSErrorEvent;

/** Emitted once per generation with updated graph state. */
export interface WSGenerationEvent {
  type: "generation";
  generation: number;
  graph: ArchGraph;
  fitness: FitnessScore;
}

/** Emitted for each individual mutation within a generation. */
export interface WSMutationEvent {
  type: "mutation";
  mutation: Mutation;
}

/** Emitted when an agent produces a message during the debate phase. */
export interface WSAgentEvent {
  type: "agent_message";
  message: AgentMessage;
}

/** Emitted when the full evolution run completes. */
export interface WSCompleteEvent {
  type: "complete";
  result: EvolutionResult;
}

/** Emitted on any backend error during evolution. */
export interface WSErrorEvent {
  type: "error";
  code: string;
  message: string;
}

// ─── API Request / Response ──────────────────────────────────────────────────

/** Request body for POST /architecture/create */
export interface CreateArchitectureRequest {
  /** Natural-language intent string from the user */
  intent: string;
  /** Optional seed for reproducible random graph generation */
  seed?: number;
  /** Preferred initial node count [3, 50] */
  initialNodes?: number;
}

/** Request body for POST /evolve */
export interface EvolveRequest {
  /** ID of the architecture to evolve */
  architectureId: string;
  /** Number of generations to run [1, 500] */
  generations: number;
  /** Optional population size override [10, 200] */
  populationSize?: number;
  /** Whether to enable the full multi-agent debate each generation */
  enableDebate?: boolean;
}

/** System status response for GET /api/v1/status */
export interface SystemStatus {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  uptime: number;
  services: {
    postgres: "up" | "down";
    neo4j: "up" | "down";
    redis: "up" | "down";
    celery: "up" | "down";
  };
  activeEvolutions: number;
  totalArchitectures: number;
}
