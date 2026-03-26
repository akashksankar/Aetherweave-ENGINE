/**
 * @fileoverview AetherWeave Global Zustand Store
 *
 * Single source of truth for all client-side state:
 *   - The active architecture graph (ArchGraph | null)
 *   - Current evolution run status + fitness history
 *   - Agent debate messages from the WebSocket stream
 *   - UI control panel settings (generations, population, intent)
 *   - System service health indicators
 *
 * State is split into logical "slices" to keep selectors efficient
 * (components only re-render when their specific slice changes).
 *
 * Usage:
 *   const intent = useLoomStore(s => s.intent);
 *   const { startEvolution } = useLoomStore();
 *
 * @module store/loom-store
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type {
  ArchGraph,
  AgentMessage,
  FitnessScore,
  EvolutionConfig,
  SystemStatus,
} from "@aetherweave/shared";

/* ─── Sub-state types ─────────────────────────────────────────────────────── */

/** One entry in the fitness history timeline built from WS generation events. */
export interface FitnessHistoryPoint {
  generation: number;
  scalability: number;
  costEfficiency: number;
  futureProof: number;
  aggregate: number;
}

/** One Echo Agent debate transcript message (from DebaterAgent). */
export interface DebateMessage {
  round: 1 | 2;
  stance: "OPTIMIST" | "PESSIMIST" | "PRAGMATIST";
  content: string;
  vote: "ACCEPT" | "REJECT" | "MODIFY" | null;
}

/** Agent debate snapshot for the current generation. */
export interface AgentDebateSnapshot {
  messages: AgentMessage[];
  transcript: DebateMessage[];
  consensus: boolean;
  criticScore: number;
  futuristScore: number;
  proposal: string;
}

/** Evolution run state machine status. */
export type EvolutionStatus =
  | "idle"
  | "connecting"
  | "running"
  | "complete"
  | "error";

/* ─── Store shape ─────────────────────────────────────────────────────────── */

export interface LoomStore {
  /* ── Architecture ─────────────────────────────────────────────────────── */
  /** Currently active architecture graph (null before first creation). */
  activeGraph: ArchGraph | null;
  /** ID of the active architecture in PostgreSQL. */
  activeGraphId: string | null;
  /** All graphs from the list endpoint (used by sidebar history panel). */
  graphList: { id: string; name: string; generation: number; fitness: { aggregate: number }; createdAt: string }[];

  /* ── Evolution run ─────────────────────────────────────────────────────── */
  evolutionStatus: EvolutionStatus;
  currentGeneration: number;
  fitnessHistory: FitnessHistoryPoint[];
  latestFitness: FitnessScore | null;
  agentDebate: AgentDebateSnapshot | null;
  /** All agent messages received so far in this run (for the speech-bubble feed). */
  agentMessages: AgentMessage[];
  evolutionError: string | null;

  /* ── UI control panel ─────────────────────────────────────────────────── */
  intent: string;
  evolutionConfig: EvolutionConfig;
  /** Sidebar open/closed on mobile. */
  sidebarOpen: boolean;
  /** Which panel is shown in the sidebar: "control" | "history" | "debate". */
  activePanel: "control" | "history" | "debate";

  /* ── System health ─────────────────────────────────────────────────────── */
  systemStatus: SystemStatus | null;
  lastStatusCheck: Date | null;

  /* ── Actions ──────────────────────────────────────────────────────────── */
  setIntent: (intent: string) => void;
  setEvolutionConfig: (config: Partial<EvolutionConfig>) => void;
  setSidebarOpen: (open: boolean) => void;
  setActivePanel: (panel: "control" | "history" | "debate") => void;

  /** Called when a new graph is created via POST /architecture/create. */
  setActiveGraph: (graph: ArchGraph) => void;
  /** Called when the graph list is fetched. */
  setGraphList: (list: LoomStore["graphList"]) => void;

  /** Begin evolution run — sets status to "connecting". */
  startEvolution: () => void;
  /** Called by the WebSocket hook on successful connection. */
  onEvolutionConnected: () => void;
  /** Called by the WebSocket hook on each WSGenerationEvent. */
  onGenerationEvent: (event: {
    generation: number;
    graph: ArchGraph;
    fitness: FitnessScore;
    agentDebate: AgentDebateSnapshot | null;
  }) => void;
  /** Called by the WebSocket hook on WSCompleteEvent. */
  onEvolutionComplete: (result: {
    bestGraph: ArchGraph;
    fitnessHistory: number[];
  }) => void;
  /** Called by the WebSocket hook on error. */
  onEvolutionError: (message: string) => void;
  /** Reset evolution state (called when user starts a new run). */
  resetEvolution: () => void;

  /** Called when system status check completes. */
  setSystemStatus: (status: SystemStatus) => void;
}

/* ─── Default evolution config ────────────────────────────────────────────── */

const DEFAULT_CONFIG: EvolutionConfig = {
  generations:      20,
  populationSize:   20,
  crossoverRate:    0.7,
  mutationRate:     0.3,
  enableMutation:   true,
  enableDebate:     true,
  enableSymbiosis:  false,
  enableForesight:  true,
  targetFitness:    0.85,
};

/* ─── Store factory ───────────────────────────────────────────────────────── */

export const useLoomStore = create<LoomStore>()(
  subscribeWithSelector((set, get) => ({
    /* ── Initial state ──────────────────────────────────────────────────── */
    activeGraph:      null,
    activeGraphId:    null,
    graphList:        [],

    evolutionStatus:  "idle",
    currentGeneration: 0,
    fitnessHistory:   [],
    latestFitness:    null,
    agentDebate:      null,
    agentMessages:    [],
    evolutionError:   null,

    intent:           "",
    evolutionConfig:  DEFAULT_CONFIG,
    sidebarOpen:      false,
    activePanel:      "control",

    systemStatus:     null,
    lastStatusCheck:  null,

    /* ── UI actions ─────────────────────────────────────────────────────── */
    setIntent:         (intent) => set({ intent }),
    setEvolutionConfig: (config) =>
      set((s) => ({ evolutionConfig: { ...s.evolutionConfig, ...config } })),
    setSidebarOpen:    (open)  => set({ sidebarOpen: open }),
    setActivePanel:    (panel) => set({ activePanel: panel }),

    /* ── Architecture actions ────────────────────────────────────────────── */
    setActiveGraph: (graph) =>
      set({ activeGraph: graph, activeGraphId: graph.id }),
    setGraphList: (list) => set({ graphList: list }),

    /* ── Evolution actions ───────────────────────────────────────────────── */
    startEvolution: () =>
      set({
        evolutionStatus:    "connecting",
        currentGeneration:  0,
        fitnessHistory:     [],
        agentMessages:      [],
        agentDebate:        null,
        evolutionError:     null,
      }),

    onEvolutionConnected: () => set({ evolutionStatus: "running" }),

    onGenerationEvent: ({ generation, graph, fitness, agentDebate }) => {
      const point: FitnessHistoryPoint = {
        generation,
        scalability:    fitness.scalability,
        costEfficiency: fitness.costEfficiency,
        futureProof:    fitness.futureProof,
        aggregate:      fitness.aggregate,
      };

      set((s) => ({
        currentGeneration: generation,
        activeGraph:       graph,
        latestFitness:     fitness,
        fitnessHistory:    [...s.fitnessHistory, point],
        agentDebate:       agentDebate ?? s.agentDebate,
        agentMessages:     agentDebate
          ? [...s.agentMessages, ...agentDebate.messages]
          : s.agentMessages,
      }));
    },

    onEvolutionComplete: ({ bestGraph, fitnessHistory }) =>
      set({
        evolutionStatus: "complete",
        activeGraph:      bestGraph,
      }),

    onEvolutionError: (message) =>
      set({ evolutionStatus: "error", evolutionError: message }),

    resetEvolution: () =>
      set({
        evolutionStatus:   "idle",
        currentGeneration: 0,
        fitnessHistory:    [],
        agentMessages:     [],
        agentDebate:       null,
        evolutionError:    null,
        latestFitness:     null,
      }),

    /* ── System status ───────────────────────────────────────────────────── */
    setSystemStatus: (status) =>
      set({ systemStatus: status, lastStatusCheck: new Date() }),
  }))
);
