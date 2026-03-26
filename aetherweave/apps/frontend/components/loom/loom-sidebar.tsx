"use client";

/**
 * @fileoverview LoomSidebar — Intent Input + Agent Controls Panel
 *
 * The sidebar is the primary interaction surface for the user to:
 * 1. Enter a natural-language architecture intent.
 * 2. Configure evolution parameters (generations, population size).
 * 3. Toggle individual LangGraph agents on/off.
 * 4. Trigger the evolution run.
 *
 * Responsive strategy:
 * - On mobile this is rendered inside a slide-over drawer (no inline layout).
 * - On desktop (md+) it is a fixed 320px left panel with its own scroll.
 *
 * @module components/loom/loom-sidebar
 */

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Zap, Brain, Eye, Clock, MessageSquare, X,
  ChevronDown, ChevronUp, Loader2,
} from "lucide-react";

/* ─── Agent toggle data ───────────────────────────────────────────────────── */

/** Static definition of each LangGraph agent shown in the sidebar. */
const AGENTS = [
  {
    id: "architect",
    label: "ArchitectAgent",
    icon: Brain,
    color: "text-aether-400",
    description: "Proposes new nodes and structural changes",
  },
  {
    id: "critic",
    label: "CriticAgent",
    icon: Eye,
    color: "text-synapse-400",
    description: "Scores fitness and identifies bottlenecks",
  },
  {
    id: "futurist",
    label: "FuturistAgent",
    icon: Clock,
    color: "text-mutagen-300",
    description: "Monte-Carlo foresight over 2–5 year horizon",
  },
  {
    id: "debater",
    label: "DebaterAgent",
    icon: MessageSquare,
    color: "text-green-400",
    description: "Echo Agents: runs multi-position debate",
  },
] as const;

type AgentId = (typeof AGENTS)[number]["id"];

/* ─── Props ──────────────────────────────────────────────────────────────── */

interface LoomSidebarProps {
  /** Callback invoked when the mobile close (×) button is tapped. */
  onClose?: () => void;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * LoomSidebar — left-panel control surface.
 *
 * @param props.onClose - Closes the mobile drawer (undefined on desktop).
 * @returns Scrollable dark panel with intent textarea, config sliders,
 *          agent toggles, and the Evolve action button.
 */
export function LoomSidebar({ onClose }: LoomSidebarProps) {
  const [intent, setIntent] = useState("");
  const [generations, setGenerations] = useState(20);
  const [population, setPopulation] = useState(20);
  const [activeAgents, setActiveAgents] = useState<Set<AgentId>>(
    new Set(AGENTS.map((a) => a.id))
  );
  const [isEvolving, setIsEvolving] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  /**
   * Toggles an agent on/off.
   * At least one agent must always remain active to prevent stalling.
   *
   * @param id - Agent identifier string.
   */
  const toggleAgent = (id: AgentId) => {
    setActiveAgents((prev) => {
      const next = new Set(prev);
      if (next.has(id) && next.size > 1) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  /**
   * Initiates the evolution run.
   * TODO (Part 2+): wire this to the Zustand store + backend API.
   */
  const handleEvolve = async () => {
    if (!intent.trim() || isEvolving) return;
    setIsEvolving(true);
    // Placeholder: actual API call introduced in Part 2
    await new Promise((r) => setTimeout(r, 2000));
    setIsEvolving(false);
  };

  return (
    <aside className="h-full flex flex-col bg-void-900/90 backdrop-blur-md border-r border-white/5 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          >
            <Zap size={16} className="text-aether-400" />
          </motion.div>
          <span className="font-display font-semibold text-sm text-gradient-aether">
            AetherWeave
          </span>
        </div>
        {/* Close button — only visible on mobile (onClose defined) */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close sidebar"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* ── Scrollable content ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">

        {/* Intent input */}
        <section className="space-y-2">
          <label
            htmlFor="intent-input"
            className="block text-xs font-medium text-muted-foreground uppercase tracking-wider"
          >
            Architecture Intent
          </label>
          <textarea
            id="intent-input"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="e.g. &quot;A real-time analytics platform for 10M daily users with ML inference…&quot;"
            rows={5}
            className="
              w-full rounded-md
              bg-void-800 border border-white/10
              text-sm text-foreground placeholder:text-muted-foreground/60
              px-3 py-2
              resize-none
              focus:outline-none focus:ring-2 focus:ring-aether-400/60 focus:border-aether-400/40
              transition-colors duration-200
              font-sans
            "
            aria-label="Describe the architecture you want to evolve"
          />
          <p className="text-xs text-muted-foreground">
            {intent.length}/2000 characters
          </p>
        </section>

        {/* Agent toggles */}
        <section className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Active Agents
          </p>
          <div className="space-y-1.5">
            {AGENTS.map((agent) => {
              const Icon = agent.icon;
              const active = activeAgents.has(agent.id);
              return (
                <motion.button
                  key={agent.id}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => toggleAgent(agent.id)}
                  className={`
                    w-full flex items-start gap-3 p-2.5 rounded-md
                    border transition-all duration-200 text-left
                    ${active
                      ? "border-white/10 bg-void-800 shadow-sm"
                      : "border-white/5 bg-void-900 opacity-50"
                    }
                  `}
                  aria-pressed={active}
                  aria-label={`${active ? "Disable" : "Enable"} ${agent.label}`}
                >
                  <Icon size={15} className={`mt-0.5 flex-shrink-0 ${agent.color}`} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground font-mono">
                      {agent.label}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5 leading-snug">
                      {agent.description}
                    </p>
                  </div>
                  <div
                    className={`ml-auto w-2 h-2 rounded-full flex-shrink-0 mt-1 transition-colors ${
                      active ? "bg-aether-400 animate-aether-pulse" : "bg-void-600"
                    }`}
                  />
                </motion.button>
              );
            })}
          </div>
        </section>

        {/* Advanced config (collapsible) */}
        <section>
          <button
            onClick={() => setAdvancedOpen((v) => !v)}
            className="flex items-center justify-between w-full text-xs font-medium text-muted-foreground uppercase tracking-wider py-1"
            aria-expanded={advancedOpen}
          >
            <span>Advanced Config</span>
            {advancedOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          <motion.div
            initial={false}
            animate={{ height: advancedOpen ? "auto" : 0, opacity: advancedOpen ? 1 : 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pt-3 space-y-4">
              {/* Generations slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <label htmlFor="generations-slider" className="text-muted-foreground">
                    Generations
                  </label>
                  <span className="font-mono text-aether-300">{generations}</span>
                </div>
                <input
                  id="generations-slider"
                  type="range" min={1} max={500} step={1}
                  value={generations}
                  onChange={(e) => setGenerations(Number(e.target.value))}
                  className="w-full accent-aether-400 cursor-pointer"
                />
                <div className="flex justify-between text-xs text-muted-foreground/60">
                  <span>1</span><span>500</span>
                </div>
              </div>

              {/* Population slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <label htmlFor="population-slider" className="text-muted-foreground">
                    Population Size
                  </label>
                  <span className="font-mono text-aether-300">{population}</span>
                </div>
                <input
                  id="population-slider"
                  type="range" min={10} max={200} step={5}
                  value={population}
                  onChange={(e) => setPopulation(Number(e.target.value))}
                  className="w-full accent-aether-400 cursor-pointer"
                />
                <div className="flex justify-between text-xs text-muted-foreground/60">
                  <span>10</span><span>200</span>
                </div>
              </div>
            </div>
          </motion.div>
        </section>
      </div>

      {/* ── Footer: Evolve button ───────────────────────────────────────── */}
      <div className="p-4 border-t border-white/5 flex-shrink-0">
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleEvolve}
          disabled={!intent.trim() || isEvolving}
          className="
            w-full flex items-center justify-center gap-2
            py-2.5 rounded-md font-medium text-sm
            bg-gradient-to-r from-aether-600/80 to-synapse-600/80
            hover:from-aether-500/90 hover:to-synapse-500/90
            border border-aether-400/30 hover:border-aether-300/50
            text-aether-100
            transition-all duration-300
            disabled:opacity-50 disabled:cursor-not-allowed
            shadow-aether-glow/0 hover:shadow-aether-glow
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-aether-400
          "
          aria-busy={isEvolving}
          aria-label="Start evolutionary run"
        >
          {isEvolving ? (
            <>
              <Loader2 size={15} className="animate-spin" />
              Evolving…
            </>
          ) : (
            <>
              <Zap size={15} />
              Evolve {generations > 0 ? `${generations} Gens` : ""}
            </>
          )}
        </motion.button>
      </div>
    </aside>
  );
}
