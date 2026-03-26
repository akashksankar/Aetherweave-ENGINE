/**
 * @fileoverview AetherWeave Root Page (Part 5 — R3F Neural Forest)
 *
 * The LoomCanvas is dynamically imported with { ssr: false } to prevent
 * Next.js from attempting to server-render the WebGL context.
 *
 * Layout: identical to Part 4 — fixed sidebar left, canvas right.
 * The CanvasPlaceholder is replaced by the real 3D LoomCanvas.
 *
 * @module app/page
 */

"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { EnhancedLoomSidebar } from "@/components/loom/loom-sidebar-enhanced";
import { useLoomStore } from "@/store/loom-store";

/**
 * Dynamically import LoomCanvas with ssr: false.
 *
 * WebGL APIs (THREE.js, canvas element) are browser-only.
 * Dynamic import avoids SSR errors during Next.js build and hydration.
 */
const LoomCanvas = dynamic(
  () =>
    import("@/components/canvas/loom-canvas").then((m) => ({
      default: m.LoomCanvas,
    })),
  {
    ssr:     false,
    loading: () => (
      /* Minimal placeholder while the JS bundle loads */
      <div className="absolute inset-0 flex items-center justify-center bg-void-950">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-aether-500 border-t-transparent animate-spin" />
          <span className="text-[11px] font-mono text-void-500">
            Loading neural forest…
          </span>
        </div>
      </div>
    ),
  }
);

/**
 * Root LoomPage component.
 *
 * @returns Full-screen AetherWeave layout.
 */
export default function LoomPage(): React.JSX.Element {
  const [mobileOpen, setMobileOpen] = useState(false);
  const evolutionStatus = useLoomStore((s) => s.evolutionStatus);
  const activeGraph     = useLoomStore((s) => s.activeGraph);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-void-950">

      {/* ── Desktop sidebar ───────────────────────────────────────────────── */}
      <aside
        className="hidden lg:flex lg:flex-col lg:w-72 lg:shrink-0 lg:border-r lg:border-void-800/60 h-full"
        aria-label="Loom control panel"
      >
        <EnhancedLoomSidebar />
      </aside>

      {/* ── Mobile drawer ────────────────────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-30 bg-black/70 backdrop-blur-sm lg:hidden"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <motion.aside
              key="drawer"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 280, damping: 28 }}
              className="fixed inset-y-0 left-0 z-40 w-80 lg:hidden flex flex-col"
              aria-label="Loom control panel"
            >
              <EnhancedLoomSidebar />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ── Main canvas ──────────────────────────────────────────────────── */}
      <main
        className="flex-1 relative overflow-hidden"
        aria-label="AetherWeave 3D neural forest canvas"
      >
        {/* The R3F neural forest fills the entire main area */}
        <LoomCanvas />

        {/* Node / edge count badge */}
        {activeGraph && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="
              absolute bottom-4 right-4 z-10
              px-3 py-1.5 rounded-full
              bg-void-900/80 border border-void-700/50
              backdrop-blur-md
            "
          >
            <span className="text-[11px] font-mono text-void-400 tabular-nums">
              {activeGraph.nodes?.length ?? 0} nodes ·{" "}
              {activeGraph.edges?.length ?? 0} edges
            </span>
          </motion.div>
        )}

        {/* Mobile FAB */}
        <button
          id="open-sidebar-fab"
          onClick={() => setMobileOpen(true)}
          className="
            lg:hidden absolute bottom-6 left-6 z-20
            w-12 h-12 rounded-full
            bg-aether-600 shadow-[0_0_20px_rgba(139,92,246,0.5)]
            flex items-center justify-center text-white text-xl
            hover:bg-aether-500 active:bg-aether-700
            transition-colors duration-200
            focus-visible:ring-2 focus-visible:ring-aether-400
          "
          aria-label="Open control panel"
        >
          ⚙
        </button>
      </main>
    </div>
  );
}
