/**
 * @fileoverview StatusBar — System service health indicators
 *
 * Displays real-time connection status for all AetherWeave backend services:
 * PostgreSQL, Neo4j, Redis, Celery — plus the WebSocket evolution connection.
 *
 * Data is fetched via the useSystemStatus TanStack Query hook (polls every 30s).
 *
 * @module components/loom/status-bar
 */

"use client";

import React from "react";
import { motion } from "framer-motion";
import { useSystemStatus } from "@/hooks/use-api";
import { useLoomStore } from "@/store/loom-store";

/* ─── Service indicator ──────────────────────────────────────────────────── */

interface ServiceDotProps {
  /** Service name to display. */
  label: string;
  /** "up" | "down" | "degraded" | undefined (loading). */
  status: string | undefined;
  /** Short emoji icon for the service. */
  icon: string;
}

/**
 * ServiceDot — small coloured dot + label for one service.
 *
 * Colour coding:
 *   up       → green (aether-400)
 *   degraded → amber
 *   down     → red   (synapse-400)
 *   loading  → void-500 (pulsing)
 */
function ServiceDot({ label, status, icon }: ServiceDotProps): React.JSX.Element {
  const colourClass =
    status === "up"       ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" :
    status === "degraded" ? "bg-amber-400"    :
    status === "down"     ? "bg-red-500  shadow-[0_0_6px_#ef4444]"    :
                            "bg-void-600 animate-pulse";

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px]">{icon}</span>
      <span
        className={`w-1.5 h-1.5 rounded-full ${colourClass}`}
        title={`${label}: ${status ?? "checking..."}`}
      />
      <span className="text-[10px] font-mono text-void-400 hidden sm:block">
        {label}
      </span>
    </div>
  );
}

/* ─── Realism Meter ──────────────────────────────────────────────────────── */

function RealismMeter(): React.JSX.Element {
  const activeGraph = useLoomStore((s) => s.activeGraph);
  const latestFitness = useLoomStore((s) => s.latestFitness);

  // Derive score from fitness aggregate + node count balance
  const score = activeGraph ? (latestFitness?.aggregate ?? 0.42) * 100 : 0;
  const rounded = Math.round(score);

  return (
    <div className="flex flex-col gap-1 min-w-[80px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[9px] font-mono text-void-500 uppercase">Realism</span>
        <span className="text-[9px] font-mono text-aether-400">{rounded}%</span>
      </div>
      <div className="h-1 w-full bg-void-900 rounded-full overflow-hidden border border-void-800/50">
        <motion.div
           initial={{ width: 0 }}
           animate={{ width: `${rounded}%` }}
           transition={{ duration: 1, ease: "easeOut" }}
           className="h-full bg-gradient-to-r from-synapse-500 to-aether-400 shadow-[0_0_8px_rgba(124,58,237,0.4)]"
        />
      </div>
    </div>
  );
}

/* ─── Main component ─────────────────────────────────────────────────────── */

/**
 * StatusBar component.
 *
 * Renders a slim horizontal bar at the bottom of the sidebar showing
 * all service health dots and the current evolution connection state.
 *
 * @returns JSX element.
 */
export function StatusBar(): React.JSX.Element {
  const { data: status, isLoading } = useSystemStatus();
  const evolutionStatus = useLoomStore((s) => s.evolutionStatus);
  const currentGen      = useLoomStore((s) => s.currentGeneration);
  const totalGens       = useLoomStore((s) => s.evolutionConfig.generations);

  const services = status?.services;

  const wsIndicator = {
    idle:       { label: "Idle",       color: "text-void-500" },
    connecting: { label: "Connecting…",color: "text-amber-400 animate-pulse" },
    running:    { label: `G${currentGen}/${totalGens}`, color: "text-aether-400" },
    complete:   { label: "Complete ✓", color: "text-emerald-400" },
    error:      { label: "Error ✗",    color: "text-red-400" },
  }[evolutionStatus];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.5 }}
      className="
        flex items-center justify-between gap-3
        px-3 py-2 rounded-lg
        bg-void-950/60 border border-void-800/40
        backdrop-blur-sm
      "
    >
      {/* ── Service dots ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <ServiceDot label="PG"    status={services?.postgres} icon="🐘" />
        <ServiceDot label="Neo4j" status={services?.neo4j}    icon="🕸️" />
        <ServiceDot label="Redis" status={services?.redis}    icon="⚡" />
        <ServiceDot label="Queue" status={services?.celery}   icon="📋" />
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* ── WebSocket / evolution status ─────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <RealismMeter />
        <span className={`text-[10px] font-mono font-semibold ${wsIndicator.color}`}>
          {wsIndicator.label}
        </span>
      </div>

      {/* ── Overall health badge ──────────────────────────────────────────── */}
      {status && (
        <span
          className={`
            text-[9px] font-mono px-1.5 py-0.5 rounded border
            ${status.status === "healthy"
              ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
              : "border-red-800 text-red-400 bg-red-950/30"}
          `}
        >
          {status.status.toUpperCase()}
        </span>
      )}
    </motion.div>
  );
}
