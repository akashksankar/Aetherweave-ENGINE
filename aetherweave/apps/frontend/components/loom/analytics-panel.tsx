/**
 * @fileoverview AnalyticsPanel — Sidebar panel for Neo4j analytics results
 *
 * Displays the Neo4j graph analytics results in the sidebar with:
 *   - Resilience score circular gauge
 *   - Bottleneck list (SPOF nodes with severity bars)
 *   - Cluster status (isolated / connected)
 *   - Critical path hops counter and long-path warning
 *   - Hub list (over-connected nodes)
 *
 * Data comes from the useAnalytics hook which polls the Redis-cached
 * /api/v1/analytics/{graph_id} endpoint every 60s.
 *
 * @module components/loom/analytics-panel
 */

"use client";

import React from "react";
import { motion } from "framer-motion";
import { useAnalytics } from "@/hooks/use-analytics";
import { useLoomStore } from "@/store/loom-store";
import { ParetoScatter } from "@/components/loom/pareto-scatter";

/* ─── Resilience gauge ───────────────────────────────────────────────────── */

function ResilienceGauge({ score }: { score: number }): React.JSX.Element {
  const r     = 20;
  const circ  = 2 * Math.PI * r;
  const arc   = circ * score;
  const color = score > 0.7 ? "#10b981" : score > 0.4 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex items-center gap-3">
      <svg width="52" height="52" viewBox="0 0 52 52">
        {/* Background track */}
        <circle cx="26" cy="26" r={r} fill="none"
          stroke="#1f1f2e" strokeWidth="4" />
        {/* Score arc */}
        <circle cx="26" cy="26" r={r} fill="none"
          stroke={color} strokeWidth="4"
          strokeDasharray={`${arc} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 26 26)"
        />
        {/* Score text */}
        <text x="26" y="30" textAnchor="middle" fontSize="9"
          fontFamily="monospace" fill={color} fontWeight="bold">
          {(score * 100).toFixed(0)}
        </text>
      </svg>
      <div>
        <div className="text-[11px] font-mono font-semibold text-void-200">
          Resilience Score
        </div>
        <div className="text-[10px] font-mono text-void-500">
          {score > 0.7 ? "Robust" : score > 0.4 ? "Moderate risk" : "Fragile — review SPOFs"}
        </div>
      </div>
    </div>
  );
}

/* ─── Severity bar ───────────────────────────────────────────────────────── */

function SeverityBar({ value, color }: { value: number; color: string }): React.JSX.Element {
  return (
    <div className="flex-1 h-1 rounded-full bg-void-800 overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value * 100}%` }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="h-full rounded-full"
        style={{ background: color }}
      />
    </div>
  );
}

/* ─── Main AnalyticsPanel ────────────────────────────────────────────────── */

/**
 * AnalyticsPanel — sidebar panel showing Neo4j analytics output.
 */
export function AnalyticsPanel(): React.JSX.Element {
  const activeGraphId = useLoomStore((s) => s.activeGraphId);
  const { data, isLoading, error } = useAnalytics(activeGraphId);

  if (!activeGraphId) {
    return (
      <div className="text-[11px] font-mono text-void-600 italic text-center py-6">
        Generate an architecture to view analytics.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 rounded-lg bg-void-900" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-[11px] font-mono text-red-400 text-center py-4">
        Neo4j analytics unavailable.
        <br />
        <span className="text-void-600">Ensure Neo4j is running.</span>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Resilience gauge */}
      <ResilienceGauge score={data.resilience_score} />

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Clusters",     value: data.cluster_count,    color: "#7c3aed" },
          { label: "Bottlenecks",  value: data.bottleneck_count, color: "#ef4444" },
          { label: "Hubs",         value: data.hubs.length,      color: "#f59e0b" },
        ].map(({ label, value, color }) => (
          <div key={label}
            className="rounded-lg px-2 py-2 bg-void-900/60 border border-void-800 text-center">
            <div className="text-base font-mono font-bold" style={{ color }}>
              {value}
            </div>
            <div className="text-[9px] font-mono text-void-600">{label}</div>
          </div>
        ))}
      </div>

      {/* Critical path */}
      {data.critical_path && (
        <div className="rounded-lg px-3 py-2 bg-void-900/40 border border-void-800/40 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-void-400 uppercase tracking-widest">
              Critical Path
            </span>
            <span className={`text-[11px] font-mono font-bold ${
              data.critical_path.is_long ? "text-amber-400" : "text-emerald-400"
            }`}>
              {data.critical_path.hops} hops
              {data.critical_path.is_long && " ⚠"}
            </span>
          </div>
          <div className="text-[10px] font-mono text-void-600">
            Weight: {data.critical_path.total_weight.toFixed(2)}
            {data.critical_path.is_long &&
              " · Long chain may introduce latency"}
          </div>
        </div>
      )}

      {/* Bottleneck list */}
      {data.bottlenecks.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] font-mono text-red-400 uppercase tracking-widest">
            ⚠ Single Points of Failure
          </span>
          {data.bottlenecks.slice(0, 4).map((b) => (
            <div key={b.node_id}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-void-900/40">
              <span className="text-[10px] font-mono text-void-300 truncate flex-1 min-w-0">
                {b.label}
              </span>
              <SeverityBar value={b.severity} color="#ef4444" />
              <span className="text-[9px] font-mono text-void-600 shrink-0">
                {(b.severity * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Hub list */}
      {data.hubs.length > 0 && (
        <div className="space-y-2">
          <span className="text-[10px] font-mono text-amber-400 uppercase tracking-widest">
            ⬡ Hub Nodes
          </span>
          {data.hubs.slice(0, 3).map((h) => (
            <div key={h.node_id}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-void-900/40">
              <span className="text-[10px] font-mono text-void-300 truncate flex-1 min-w-0">
                {h.label}
              </span>
              <span className="text-[9px] font-mono text-amber-500 shrink-0">
                deg {h.degree}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Pareto scatter */}
      <ParetoScatter />
    </div>
  );
}
