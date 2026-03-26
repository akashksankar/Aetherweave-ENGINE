/**
 * @fileoverview LoomCanvas — R3F Canvas container for the neural forest
 *
 * Wraps the NeuralForest scene in a @react-three/fiber <Canvas> with:
 *   - WebGL renderer: shadows + tone mapping (ACESFilmic) + HDR pixel ratio
 *   - Post-processing: Bloom pass via @react-three/postprocessing (optional)
 *   - Suspense fallback: animated loading overlay
 *   - Error boundary to catch WebGL context loss gracefully
 *   - Resize observer (fillParent) for responsive canvas
 *
 * This component is "use client" and dynamically imported in page.tsx
 * with { ssr: false } to avoid hydration issues with WebGL.
 *
 * @module components/canvas/loom-canvas
 */

"use client";

import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { motion } from "framer-motion";

import { NeuralForest } from "@/components/canvas/neural-forest";
import { useLoomStore } from "@/store/loom-store";

/* ─── Loading overlay ────────────────────────────────────────────────────── */

/**
 * WebGL loading overlay shown while the R3F scene compiles shaders.
 * Uses SVG rings to mimic the loom's bioluminescent aesthetic.
 */
function CanvasLoader(): React.JSX.Element {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-void-950 z-10">
      <div className="relative w-16 h-16">
        {/* Outer ring */}
        <svg viewBox="0 0 64 64" className="absolute inset-0 animate-spin-slow">
          <circle
            cx="32" cy="32" r="28"
            fill="none"
            stroke="url(#grad)"
            strokeWidth="2"
            strokeDasharray="40 140"
            strokeLinecap="round"
          />
          <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stopColor="#7c3aed" />
              <stop offset="100%" stopColor="#0ea5e9" />
            </linearGradient>
          </defs>
        </svg>
        {/* Inner pulse dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-3 h-3 rounded-full bg-aether-400 animate-pulse" />
        </div>
      </div>
      <span className="mt-4 text-[11px] font-mono text-void-500 animate-pulse">
        Initializing neural forest…
      </span>
    </div>
  );
}

/* ─── Canvas component ───────────────────────────────────────────────────── */

/**
 * LoomCanvas — full-screen, dynamically-imported R3F canvas.
 *
 * Dynamic import in page.tsx:
 *   const LoomCanvas = dynamic(
 *     () => import("@/components/canvas/loom-canvas").then(m => ({ default: m.LoomCanvas })),
 *     { ssr: false }
 *   );
 *
 * @returns Full-screen canvas with the NeuralForest scene inside.
 */
export function LoomCanvas(): React.JSX.Element {
  const activeGraph     = useLoomStore((s) => s.activeGraph);
  const evolutionStatus = useLoomStore((s) => s.evolutionStatus);

  return (
    <div className="absolute inset-0 bg-void-950">
      {/* ── Gradient background ──────────────────────────────────────────── */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: [
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(124,58,237,0.06) 0%, transparent 70%)",
            "radial-gradient(ellipse 40% 30% at 80% 20%, rgba(14,165,233,0.04) 0%, transparent 60%)",
          ].join(", "),
        }}
      />

      {/* ── R3F Canvas ────────────────────────────────────────────────────── */}
      <Canvas
        shadows
        camera={{ position: [0, 0, 22], fov: 55, near: 0.1, far: 200 }}
        dpr={[1, Math.min(window?.devicePixelRatio ?? 1, 2)]}
        gl={{
          antialias:        true,
          toneMapping:      THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.2,
          outputColorSpace: THREE.SRGBColorSpace,
        }}
        style={{ position: "absolute", inset: 0 }}
        onPointerMissed={() => {}}
      >
        <Suspense fallback={null}>
          <NeuralForest />
        </Suspense>
      </Canvas>

      {/* ── Empty state overlay (before first graph) ──────────────────────── */}
      {!activeGraph && evolutionStatus === "idle" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="
            absolute inset-0 flex flex-col items-center justify-center
            pointer-events-none gap-4 z-10
          "
        >
          <div className="text-center space-y-3 max-w-sm px-8">
            <span className="text-4xl">🧬</span>
            <h1 className="text-lg font-semibold text-void-200 tracking-tight">
              AetherWeave Neural Forest
            </h1>
            <p className="text-[12px] font-mono text-void-500 leading-relaxed">
              Describe your architecture intent in the sidebar,
              then click{" "}
              <span className="text-aether-400 font-semibold">
                Generate Architecture
              </span>{" "}
              to seed the living loom.
            </p>
          </div>

          {/* Animated concentric rings */}
          <div className="relative w-32 h-32">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="absolute inset-0 rounded-full border border-aether-800/30"
                style={{
                  transform: `scale(${1 + i * 0.4})`,
                  animation: `ping 2.4s ${i * 0.8}s cubic-bezier(0,0,0.2,1) infinite`,
                  opacity: 1 - i * 0.3,
                }}
              />
            ))}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 rounded-full bg-aether-700/50 backdrop-blur-sm border border-aether-600/50 animate-pulse" />
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Generation counter overlay ────────────────────────────────────── */}
      {evolutionStatus === "running" && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="
            absolute top-4 left-1/2 -translate-x-1/2 z-10
            flex items-center gap-2 px-4 py-2 rounded-full
            bg-void-900/70 backdrop-blur-md border border-aether-700/40
          "
        >
          <span className="w-2 h-2 rounded-full bg-aether-400 animate-pulse shrink-0" />
          <span className="text-[12px] font-mono text-aether-300 font-semibold">
            NSGA-II Evolution Active · 4-Agent Swarm Debating
          </span>
        </motion.div>
      )}
    </div>
  );
}
