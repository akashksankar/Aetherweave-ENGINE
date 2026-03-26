"use client";

/**
 * @fileoverview CanvasPlaceholder — 3D Neural Loom Canvas Placeholder
 *
 * This component occupies the main canvas area before the full React Three
 * Fiber scene is implemented in Part 5.
 *
 * It renders:
 * 1. An animated CSS gradient that mimics the depth of a 3D loom.
 * 2. Floating pseudo-node circles with pulse animations.
 * 3. SVG connector lines between them (static preview).
 * 4. An overlay text banner inviting the user to enter an intent.
 *
 * The component fills 100% of its parent container; the parent
 * (LoomShell's <main>) is sized via the canvas-fill utility.
 *
 * @module components/loom/canvas-placeholder
 */

import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

/** A single floating pseudo-node for the demo preview. */
interface DemoNode {
  id: number;
  cx: string; // as percentage string
  cy: string;
  r: number;
  color: string;
  delay: number;
  label: string;
}

/** Static preview nodes — replaced by real ArchNode data in Part 5. */
const DEMO_NODES: DemoNode[] = [
  { id: 0, cx: "20%", cy: "30%", r: 18, color: "#22d3ee", delay: 0,    label: "gateway" },
  { id: 1, cx: "40%", cy: "20%", r: 14, color: "#a78bfa", delay: 0.5,  label: "auth" },
  { id: 2, cx: "60%", cy: "35%", r: 20, color: "#22d3ee", delay: 1,    label: "service" },
  { id: 3, cx: "75%", cy: "55%", r: 16, color: "#fbbf24", delay: 1.5,  label: "ml" },
  { id: 4, cx: "35%", cy: "65%", r: 15, color: "#4ade80", delay: 0.8,  label: "database" },
  { id: 5, cx: "55%", cy: "75%", r: 12, color: "#a78bfa", delay: 1.2,  label: "cache" },
  { id: 6, cx: "80%", cy: "25%", r: 13, color: "#22d3ee", delay: 0.3,  label: "cdn" },
];

/** Static edge pairs (as indices into DEMO_NODES). */
const DEMO_EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 2], [2, 3],
  [2, 4], [3, 5], [4, 5], [2, 6], [6, 3],
];

/**
 * CanvasPlaceholder — animated preview of the 3D loom before Part 5.
 *
 * Uses an SVG foreign-object pattern to position nodes over a gradient canvas.
 * All positions use viewBox-relative percentages so the layout is inherently
 * responsive across any container size.
 *
 * @returns Full-fill animated canvas preview with floating nodes and edges.
 */
export function CanvasPlaceholder() {
  const svgRef = useRef<SVGSVGElement>(null);

  /**
   * On mount, assign random GSAP-like drift animations via CSS custom props.
   * This creates the impression of slow 3D float without a WebGL context.
   */
  useEffect(() => {
    // Nothing to animate via JS here — all handled by Framer Motion.
  }, []);

  return (
    <div
      className="relative w-full h-full overflow-hidden"
      role="img"
      aria-label="AetherWeave architecture preview canvas"
    >
      {/* ── Background radial gradient — depth illusion ───────────────── */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 70% 60% at 60% 40%, hsl(185 90% 8% / 0.8) 0%, transparent 70%),
            radial-gradient(ellipse 50% 50% at 20% 70%, hsl(270 70% 8% / 0.6) 0%, transparent 60%),
            hsl(240 20% 4%)
          `,
        }}
      />

      {/* ── Scanline overlay — cyber aesthetic ───────────────────────── */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.5) 2px, rgba(255,255,255,0.5) 3px)",
        }}
      />

      {/* ── SVG node graph ────────────────────────────────────────────── */}
      <svg
        ref={svgRef}
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          {/* Glow filter for nodes */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Edges (mycelium lines) */}
        {DEMO_EDGES.map(([a, b]) => {
          const na = DEMO_NODES[a];
          const nb = DEMO_NODES[b];
          return (
            <line
              key={`${a}-${b}`}
              x1={na.cx} y1={na.cy}
              x2={nb.cx} y2={nb.cy}
              stroke="rgba(34,211,238,0.15)"
              strokeWidth="0.4"
              strokeDasharray="1 1.5"
            />
          );
        })}

        {/* Nodes */}
        {DEMO_NODES.map((node) => (
          <g key={node.id} filter="url(#glow)">
            <circle
              cx={node.cx} cy={node.cy}
              r={node.r / 8}
              fill={node.color}
              fillOpacity={0.15}
              stroke={node.color}
              strokeWidth="0.3"
            />
          </g>
        ))}
      </svg>

      {/* ── Framer Motion floating node labels ───────────────────────── */}
      {DEMO_NODES.map((node) => (
        <motion.div
          key={node.id}
          className="absolute font-mono text-xs pointer-events-none select-none"
          style={{
            left: node.cx,
            top:  node.cy,
            color: node.color,
            textShadow: `0 0 8px ${node.color}`,
          }}
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{
            opacity: [0.5, 0.9, 0.5],
            y: [0, -4, 0],
          }}
          transition={{
            duration: 4 + node.delay,
            repeat: Infinity,
            delay: node.delay,
            ease: "easeInOut",
          }}
        >
          {node.label}
        </motion.div>
      ))}

      {/* ── Centre overlay prompt ────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.5 }}
        className="
          absolute inset-0 flex flex-col items-center justify-center
          pointer-events-none select-none p-4
        "
      >
        <div className="glass-card px-6 py-5 text-center space-y-3 max-w-sm w-full">
          <motion.div
            animate={{ rotate: [0, 360] }}
            transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
            className="inline-block"
          >
            <Sparkles size={28} className="text-aether-400 mx-auto" />
          </motion.div>
          <h2 className="text-base font-display font-semibold text-gradient-aether">
            Neural Loom Ready
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Enter your architecture intent in the{" "}
            <span className="text-aether-300">sidebar</span> and press{" "}
            <span className="text-aether-300">Evolve</span> to grow your living architecture.
          </p>
          <p className="text-xs text-muted-foreground/60">
            3D canvas activates in Part 5 → React Three Fiber
          </p>
        </div>
      </motion.div>
    </div>
  );
}
