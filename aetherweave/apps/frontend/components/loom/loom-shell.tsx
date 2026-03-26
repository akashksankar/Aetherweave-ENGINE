"use client";

/**
 * @fileoverview LoomShell — Top-Level Application Shell
 *
 * Composes the full-screen responsive layout:
 * - A collapsible sidebar (left panel) for intent input and agent controls.
 * - The 3D neural loom canvas (center/right, full remaining viewport).
 * - A mobile header with hamburger to toggle the sidebar.
 *
 * Responsive behaviour:
 * ┌─────────────────────────────────────────────────┐
 * │ Mobile (<768px)                                 │
 * │  ┌──────────────────────────────────────────┐   │
 * │  │ Header: [☰ AetherWeave]           [...]  │   │
 * │  ├──────────────────────────────────────────┤   │
 * │  │        3D Canvas (full screen)           │   │
 * │  └──────────────────────────────────────────┘   │
 * │  Sidebar slides in as a drawer from the left.   │
 * └─────────────────────────────────────────────────┘
 * ┌─────────────────────────────────────────────────┐
 * │ Desktop (≥1024px)                               │
 * │  ┌──────────┬──────────────────────────────┐    │
 * │  │ Sidebar  │                              │    │
 * │  │  320px   │      3D Canvas               │    │
 * │  │  fixed   │      (remaining width)       │    │
 * │  │          │                              │    │
 * │  └──────────┴──────────────────────────────┘    │
 * └─────────────────────────────────────────────────┘
 *
 * @module components/loom/loom-shell
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Zap, GitBranch, Compass } from "lucide-react";
import { LoomSidebar } from "./loom-sidebar";
import { CanvasPlaceholder } from "./canvas-placeholder";
import { SectionErrorBoundary } from "@/components/error-boundary";

/* ─── Constants ──────────────────────────────────────────────────────────── */

/** CSS variable name injected into :root so canvas-fill utility works. */
const SIDEBAR_W_VAR = "--sidebar-w";

/** Desktop sidebar width in pixels. */
const DESKTOP_SIDEBAR_W = 320;

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * LoomShell — full-screen application chrome.
 *
 * State:
 * - `sidebarOpen` — controls mobile drawer visibility.
 *
 * Side effects:
 * - Injects `--sidebar-w` CSS variable on mount and window resize so that
 *   the canvas-fill utility always knows the available width.
 *
 * @returns The composited layout with sidebar + canvas + mobile header.
 */
export function LoomShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const headerRef = useRef<HTMLElement>(null);

  /**
   * Update `--sidebar-w` and `--header-h` on the root element.
   * Runs on mount and on every resize event.
   * This ensures the WebGL canvas always fits exactly in the remaining space.
   */
  const updateCSSVars = useCallback(() => {
    const isMd = window.matchMedia("(min-width: 768px)").matches;
    const sidebarW = isMd ? DESKTOP_SIDEBAR_W : 0;
    const headerH = headerRef.current?.offsetHeight ?? 0;

    document.documentElement.style.setProperty(SIDEBAR_W_VAR, `${sidebarW}px`);
    document.documentElement.style.setProperty("--header-h", `${headerH}px`);
  }, []);

  useEffect(() => {
    updateCSSVars();
    const observer = new ResizeObserver(updateCSSVars);
    observer.observe(document.documentElement);
    if (headerRef.current) observer.observe(headerRef.current);
    return () => observer.disconnect();
  }, [updateCSSVars]);

  /** Close sidebar when route changes or Escape is pressed. */
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-void-950 relative">
      {/* ── Mobile header ───────────────────────────────────────────────── */}
      <header
        ref={headerRef}
        className="
          md:hidden
          fixed top-0 inset-x-0 z-40
          flex items-center justify-between
          px-4 py-3
          bg-void-900/80 backdrop-blur-md
          border-b border-white/5
        "
      >
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ rotate: [0, 360] }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            className="text-aether-400"
          >
            <Zap size={18} className="text-aether-400" />
          </motion.div>
          <span className="font-display font-semibold text-sm text-gradient-aether">
            AetherWeave
          </span>
        </div>

        <nav className="flex items-center gap-1">
          <a
            href="/history"
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-void-700 transition-colors"
            aria-label="Evolution history"
          >
            <GitBranch size={16} />
          </a>
          <a
            href="/explore"
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-void-700 transition-colors"
            aria-label="Explore DNA library"
          >
            <Compass size={16} />
          </a>
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-void-700 transition-colors"
            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </nav>
      </header>

      {/* ── Mobile sidebar backdrop ─────────────────────────────────────── */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden fixed inset-0 z-40 bg-void-950/70 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {/* On mobile: animated drawer from the left (z-50 above backdrop) */}
        <motion.aside
          key="sidebar"
          // Mobile: slide in from left; desktop: static
          initial={false}
          animate={{
            x: sidebarOpen || typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches
              ? 0
              : "-100%",
          }}
          className="
            fixed md:static top-0 left-0
            z-50 md:z-auto
            h-full
            w-[min(320px,85vw)] md:w-[320px]
            flex-shrink-0
            mt-[var(--header-h,0px)] md:mt-0
            md:translate-x-0
          "
        >
          <SectionErrorBoundary>
            <LoomSidebar onClose={() => setSidebarOpen(false)} />
          </SectionErrorBoundary>
        </motion.aside>
      </AnimatePresence>

      {/* ── Main canvas area ─────────────────────────────────────────────── */}
      <main
        className="
          flex-1 min-w-0
          mt-[var(--header-h,0px)] md:mt-0
          relative overflow-hidden
        "
      >
        <SectionErrorBoundary>
          <CanvasPlaceholder />
        </SectionErrorBoundary>
      </main>
    </div>
  );
}
