/**
 * @fileoverview FitnessChart — Live multi-line fitness chart
 *
 * Renders a smooth animated line chart of all three fitness dimensions
 * (scalability, costEfficiency, futureProof) plus the aggregate score
 * over the evolution generation timeline.
 *
 * Built with native SVG — no external charting library required.
 * Animates new data points with a CSS transition on the SVG polyline.
 *
 * @module components/loom/fitness-chart
 */

"use client";

import React, { useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { useLoomStore } from "@/store/loom-store";
import type { FitnessHistoryPoint } from "@/store/loom-store";

/* ─── Constants ──────────────────────────────────────────────────────────── */

const CHART_H = 120;
const CHART_W = 100; // SVG viewBox percentage coords
const PAD_LEFT = 8;
const PAD_BOTTOM = 8;

/** Each line's config: key, colour, label. */
interface LineConfig {
  key: keyof Omit<FitnessHistoryPoint, "generation">;
  color: string;
  label: string;
}

const LINES: LineConfig[] = [
  { key: "aggregate",      color: "#a78bfa", label: "Aggregate"   },
  { key: "scalability",    color: "#34d399", label: "Scale"       },
  { key: "costEfficiency", color: "#fb923c", label: "Cost"        },
  { key: "futureProof",    color: "#38bdf8", label: "Future"      },
];

/* ─── Helpers ────────────────────────────────────────────────────────────── */

/**
 * Convert a series of FitnessHistoryPoints into an SVG polyline `points` string.
 *
 * Maps generation index → x axis, fitness value → y axis.
 * Y is inverted because SVG origin is top-left.
 *
 * @param data   Array of history points.
 * @param key    Which fitness dimension to plot.
 * @param total  Total expected generations (for x-axis scaling).
 * @returns SVG `points` attribute string: "x1,y1 x2,y2 ..."
 */
function toPolylinePoints(
  data: FitnessHistoryPoint[],
  key: keyof Omit<FitnessHistoryPoint, "generation">,
  total: number
): string {
  if (data.length === 0) return "";
  const xRange = Math.max(total - 1, data.length - 1, 1);

  return data
    .map((p, i) => {
      const x = PAD_LEFT + (i / xRange) * (CHART_W - PAD_LEFT);
      const y = CHART_H - PAD_BOTTOM - p[key] * (CHART_H - PAD_BOTTOM * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * FitnessChart component.
 *
 * Reads `fitnessHistory` and `evolutionConfig.generations` from the Zustand
 * store and renders a live-updating multi-line SVG chart.
 *
 * Each line is drawn as an SVG `<polyline>` with a Framer Motion initial
 * animation that fades in the chart area on first render.
 *
 * @returns A responsive fitness chart with legend.
 */
export function FitnessChart(): React.JSX.Element {
  const fitnessHistory = useLoomStore((s) => s.fitnessHistory);
  const totalGens      = useLoomStore((s) => s.evolutionConfig.generations);
  const latestFitness  = useLoomStore((s) => s.latestFitness);

  const empty = fitnessHistory.length === 0;

  /** Y-axis gridline values [0.0, 0.25, 0.5, 0.75, 1.0]. */
  const gridLines = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <div className="w-full relative">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-void-300 uppercase tracking-widest">
          Fitness Live Chart
        </span>
        {latestFitness && (
          <span className="text-xs font-mono text-aether-400 font-semibold tabular-nums">
            ↗ {latestFitness.aggregate.toFixed(4)}
          </span>
        )}
      </div>

      {/* ── Chart area ──────────────────────────────────────────────────── */}
      <motion.div
        className="relative rounded-lg overflow-hidden bg-void-950 border border-void-800"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {empty ? (
          /* Empty state */
          <div className="flex items-center justify-center h-[128px]">
            <span className="text-xs text-void-500 font-mono italic">
              No evolution data yet — click Evolve to begin
            </span>
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${CHART_W} ${CHART_H}`}
            className="w-full h-[128px]"
            preserveAspectRatio="none"
            aria-label="Fitness chart"
            role="img"
          >
            {/* Grid lines */}
            {gridLines.map((v) => {
              const y = CHART_H - PAD_BOTTOM - v * (CHART_H - PAD_BOTTOM * 2);
              return (
                <line
                  key={v}
                  x1={PAD_LEFT} y1={y}
                  x2={CHART_W}  y2={y}
                  stroke="#1e1e2e"
                  strokeWidth="0.5"
                />
              );
            })}

            {/* Data lines */}
            {LINES.map(({ key, color }) => (
              <polyline
                key={key}
                points={toPolylinePoints(fitnessHistory, key, totalGens)}
                fill="none"
                stroke={color}
                strokeWidth="1.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={key === "aggregate" ? 1 : 0.65}
              />
            ))}

            {/* Latest point glow dot on aggregate */}
            {fitnessHistory.length > 0 && (() => {
              const last   = fitnessHistory[fitnessHistory.length - 1]!;
              const xRange = Math.max(totalGens - 1, fitnessHistory.length - 1, 1);
              const cx = PAD_LEFT + ((fitnessHistory.length - 1) / xRange) * (CHART_W - PAD_LEFT);
              const cy = CHART_H - PAD_BOTTOM - last.aggregate * (CHART_H - PAD_BOTTOM * 2);
              return (
                <>
                  <circle cx={cx} cy={cy} r="2.5" fill="#a78bfa" opacity="0.3" />
                  <circle cx={cx} cy={cy} r="1.2" fill="#a78bfa" />
                </>
              );
            })()}
          </svg>
        )}
      </motion.div>

      {/* ── Legend ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 mt-2">
        {LINES.map(({ key, color, label }) => {
          const latest = latestFitness
            ? (latestFitness as Record<string, number>)[
                key === "costEfficiency" ? "costEfficiency" : key
              ]
            : null;
          return (
            <div key={key} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-1 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] font-mono text-void-400">
                {label}
                {latest !== undefined && latest !== null
                  ? ` ${(latest as number).toFixed(3)}`
                  : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
