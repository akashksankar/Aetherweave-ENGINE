/**
 * @fileoverview ParetoScatter — 3D-inspired Pareto front scatter chart
 *
 * Renders the NSGA-II Pareto front as an SVG scatter plot:
 *   X axis: Scalability fitness
 *   Y axis: Cost Efficiency fitness
 *   Dot colour: Future-proof score (blue → violet gradient)
 *   Dot size: Aggregate fitness
 *
 * The Pareto front is highlighted with a dashed envelope line.
 * Hovering a dot shows a tooltip with all 4 fitness dimensions.
 *
 * @module components/loom/pareto-scatter
 */

"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { useParetoFront } from "@/hooks/use-analytics";
import { useLoomStore } from "@/store/loom-store";
import type { ParetoIndividual } from "@/hooks/use-analytics";

/* ─── Chart constants ────────────────────────────────────────────────────── */

const W = 100;    // SVG viewBox width
const H = 80;     // SVG viewBox height
const PAD = 8;    // Padding

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function mapX(v: number): number {
  return PAD + v * (W - PAD * 2);
}

function mapY(v: number): number {
  return H - PAD - v * (H - PAD * 2);
}

/** Future-proof score [0, 1] → hex colour (cyan → violet). */
function fpColor(fp: number): string {
  const r = Math.round(14  + fp * 124);      // 14 → 138
  const g = Math.round(165 - fp * 100);      // 165 → 65
  const b = Math.round(233 - fp * 40);       // 233 → 193
  return `rgb(${r},${g},${b})`;
}

/* ─── Tooltip ────────────────────────────────────────────────────────────── */

interface TooltipProps {
  individual: ParetoIndividual;
  x: number;
  y: number;
}

function Tooltip({ individual, x, y }: TooltipProps): React.JSX.Element {
  return (
    <g>
      <rect
        x={Math.min(x, W - 36)} y={Math.max(y - 22, 2)}
        width="35" height="20" rx="2"
        fill="#0a0118" stroke="#3b1f6e" strokeWidth="0.5"
      />
      <text
        x={Math.min(x + 2, W - 34)} y={Math.max(y - 13, 9)}
        fontSize="3" fill="#c4b5fd" fontFamily="monospace"
      >
        {`G${individual.generation} R${individual.rank}`}
      </text>
      <text
        x={Math.min(x + 2, W - 34)} y={Math.max(y - 8, 14)}
        fontSize="2.8" fill="#a78bfa" fontFamily="monospace"
      >
        {`∑ ${(individual.aggregate * 100).toFixed(0)}%`}
      </text>
      <text
        x={Math.min(x + 2, W - 34)} y={Math.max(y - 4, 18)}
        fontSize="2.4" fill="#6b7280" fontFamily="monospace"
      >
        {`sc:${(individual.scalability * 100).toFixed(0)} co:${(individual.cost_efficiency * 100).toFixed(0)} fu:${(individual.future_proof * 100).toFixed(0)}`}
      </text>
    </g>
  );
}

/* ─── Main component ─────────────────────────────────────────────────────── */

/**
 * ParetoScatter — SVG scatter chart of NSGA-II Pareto front individuals.
 *
 * @returns JSX element with the scatter chart, axes, and legend.
 */
export function ParetoScatter(): React.JSX.Element {
  const activeGraphId = useLoomStore((s) => s.activeGraphId);
  const { data, isLoading } = useParetoFront(activeGraphId);
  const [hovered, setHovered] = useState<number | null>(null);

  const individuals = data?.individuals ?? [];
  const empty = individuals.length === 0;

  return (
    <div className="w-full space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono text-void-400 uppercase tracking-widest">
          Pareto Front
        </span>
        <span className="text-[10px] font-mono text-void-600">
          {data?.front_size ?? 0} optimal · {data?.dominated ?? 0} dominated
        </span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-lg border border-void-800 bg-void-950 overflow-hidden"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-24">
            <span className="text-[10px] font-mono text-void-600 animate-pulse">
              Running NSGA-II analysis…
            </span>
          </div>
        ) : empty ? (
          <div className="flex flex-col items-center justify-center h-24 gap-1">
            <span className="text-xl opacity-30">📊</span>
            <span className="text-[10px] font-mono text-void-600 italic">
              Pareto front available after first evolution
            </span>
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-36"
            style={{ overflow: "visible" }}
          >
            {/* Grid lines */}
            {[0.25, 0.5, 0.75].map((v) => (
              <React.Fragment key={v}>
                <line
                  x1={mapX(0)} y1={mapY(v)} x2={mapX(1)} y2={mapY(v)}
                  stroke="#1e1e2e" strokeWidth="0.4"
                />
                <line
                  x1={mapX(v)} y1={mapY(0)} x2={mapX(v)} y2={mapY(1)}
                  stroke="#1e1e2e" strokeWidth="0.4"
                />
              </React.Fragment>
            ))}

            {/* Axis labels */}
            <text x={W / 2} y={H - 1} fontSize="3.5" fill="#4b5563" textAnchor="middle" fontFamily="monospace">
              Scalability →
            </text>
            <text x={3} y={H / 2} fontSize="3.5" fill="#4b5563" textAnchor="middle"
              fontFamily="monospace"
              transform={`rotate(-90, 3, ${H / 2})`}
            >
              Cost Eff →
            </text>

            {/* Pareto step envelope */}
            {individuals.length >= 2 && (() => {
              const sorted = [...individuals].sort((a, b) => a.scalability - b.scalability);
              const pts = sorted.map((ind) =>
                `${mapX(ind.scalability).toFixed(1)},${mapY(ind.cost_efficiency).toFixed(1)}`
              ).join(" ");
              return (
                <polyline
                  points={pts}
                  fill="none"
                  stroke="#7c3aed"
                  strokeWidth="0.6"
                  strokeDasharray="2 1.5"
                  opacity="0.5"
                />
              );
            })()}

            {/* Data points */}
            {individuals.map((ind, i) => {
              const cx = mapX(ind.scalability);
              const cy = mapY(ind.cost_efficiency);
              const r  = 1.2 + ind.aggregate * 1.8;
              const col = fpColor(ind.future_proof);
              const isHovered = hovered === i;

              return (
                <g key={i}>
                  {/* Glow */}
                  <circle
                    cx={cx} cy={cy} r={r * 2.5}
                    fill={col} opacity="0.06"
                  />
                  {/* Main dot */}
                  <circle
                    cx={cx} cy={cy}
                    r={isHovered ? r * 1.5 : r}
                    fill={col}
                    opacity={isHovered ? 1 : 0.8}
                    style={{ cursor: "pointer", transition: "r 0.15s" }}
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                  />
                  {/* Rank label for front members */}
                  {ind.rank === 0 && (
                    <text cx={cx} cy={cy - r - 1} fontSize="2.2" fill="#a78bfa"
                      textAnchor="middle" fontFamily="monospace">
                      ★
                    </text>
                  )}
                </g>
              );
            })}

            {/* Tooltip */}
            {hovered !== null && individuals[hovered] && (() => {
              const ind = individuals[hovered]!;
              return (
                <Tooltip
                  individual={ind}
                  x={mapX(ind.scalability)}
                  y={mapY(ind.cost_efficiency)}
                />
              );
            })()}
          </svg>
        )}
      </motion.div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-[9px] font-mono text-void-600">
        <span>●  future-proof (cyan→violet)</span>
        <span>●  size = aggregate fitness</span>
        <span>★  rank-0</span>
      </div>
    </div>
  );
}
