"use client";

/**
 * @fileoverview LoomLoadingSkeleton — Full-Screen Neural Growth Loading State
 *
 * Rendered by the Suspense boundary in app/page.tsx while LoomShell hydrates.
 * Mimics the final layout (sidebar + canvas) using animated skeleton blocks
 * so the user sees a structure preview rather than a blank screen.
 *
 * Responsiveness:
 * - On mobile: full-width single column (sidebar hidden during skeleton).
 * - On desktop (md+): 320px sidebar skeleton + canvas skeleton side-by-side.
 *
 * @module components/loom/loom-loading-skeleton
 */

import React from "react";
import { motion } from "framer-motion";

/* ─── Skeleton Node data ─────────────────────────────────────────────────── */

/** Positions for the floating ghost nodes in the canvas skeleton. */
const GHOST_NODES = [
  { top: "25%", left: "30%", size: 24, delay: 0 },
  { top: "45%", left: "55%", size: 18, delay: 0.3 },
  { top: "60%", left: "25%", size: 20, delay: 0.6 },
  { top: "30%", left: "70%", size: 15, delay: 0.9 },
  { top: "70%", left: "65%", size: 22, delay: 0.5 },
];

/**
 * SkeletonBlock — reusable animated placeholder block.
 *
 * @param props.className - Additional Tailwind classes for sizing/positioning.
 * @param props.delay     - Animation start delay in seconds.
 * @returns A shimmer-animated div.
 */
function SkeletonBlock({
  className = "",
  delay = 0,
}: {
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={`skeleton ${className}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: [0, 0.7, 0.4] }}
      transition={{ duration: 2, repeat: Infinity, delay, ease: "easeInOut" }}
    />
  );
}

/**
 * LoomLoadingSkeleton — full-screen layout skeleton.
 *
 * Matches the proportions of the real LoomShell layout so that
 * the layout shift when Suspense resolves is imperceptible.
 *
 * @returns Responsive dark skeleton matching the app chrome.
 */
export function LoomLoadingSkeleton() {
  return (
    <div className="flex h-dvh w-full overflow-hidden bg-void-950">

      {/* ── Sidebar skeleton (hidden on mobile) ───────────────────────── */}
      <div className="hidden md:flex w-[320px] flex-col flex-shrink-0 border-r border-white/5 p-4 space-y-4 bg-void-900">
        {/* Header */}
        <SkeletonBlock className="h-6 w-32 rounded-md" />
        {/* Intent textarea area */}
        <SkeletonBlock className="h-28 w-full rounded-md" delay={0.1} />
        {/* Agent toggles */}
        {[0, 0.15, 0.25, 0.35].map((d, i) => (
          <SkeletonBlock key={i} className="h-14 w-full rounded-md" delay={d} />
        ))}
        {/* Spacer + evolve button */}
        <div className="mt-auto pt-4 border-t border-white/5">
          <SkeletonBlock className="h-10 w-full rounded-md" delay={0.4} />
        </div>
      </div>

      {/* ── Canvas skeleton ────────────────────────────────────────────── */}
      <div className="relative flex-1 min-w-0 bg-gradient-to-br from-void-950 to-void-900 overflow-hidden">

        {/* Ghost node circles */}
        {GHOST_NODES.map((node, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full border border-aether-400/20 bg-aether-400/5"
            style={{
              top: node.top,
              left: node.left,
              width: node.size,
              height: node.size,
              transform: "translate(-50%, -50%)",
            }}
            animate={{
              opacity: [0.2, 0.6, 0.2],
              scale: [0.9, 1.1, 0.9],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              delay: node.delay,
              ease: "easeInOut",
            }}
          />
        ))}

        {/* Centre loading indicator */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
          <motion.div
            className="w-8 h-8 rounded-full border-2 border-aether-400 border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          />
          <p className="text-xs text-muted-foreground font-mono">
            Initialising neural loom…
          </p>
        </div>
      </div>
    </div>
  );
}
