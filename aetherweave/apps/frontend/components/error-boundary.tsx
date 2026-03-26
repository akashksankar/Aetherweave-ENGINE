"use client";

/**
 * @fileoverview Global Error Boundary — AetherWeave Frontend
 *
 * React's Error Boundary pattern catches JavaScript errors anywhere in the
 * child component tree, logs them, and renders a fallback UI instead of
 * crashing the entire page.
 *
 * This file exports two components:
 * - `GlobalErrorBoundary` — class-based boundary wrapping the entire app.
 * - `SectionErrorBoundary` — lightweight boundary for isolated sections.
 *
 * @module components/error-boundary
 */

import React, { Component, type ErrorInfo, type ReactNode } from "react";
import { motion } from "framer-motion";

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface ErrorBoundaryProps {
  /** The subtree to protect. */
  children: ReactNode;
  /** Optional custom fallback UI to render on error. */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  /** Whether an error has been caught. */
  hasError: boolean;
  /** The caught error for display / logging purposes. */
  error: Error | null;
}

/* ─── GlobalErrorBoundary ────────────────────────────────────────────────── */

/**
 * GlobalErrorBoundary — full page error fallback.
 *
 * Wraps the root layout. When an unhandled React error propagates here,
 * the 3D canvas and all panels are replaced by a centred error card
 * with a retry button.
 *
 * @example
 * ```tsx
 * <GlobalErrorBoundary>
 *   <App />
 * </GlobalErrorBoundary>
 * ```
 */
export class GlobalErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  /**
   * Called by React when a descendant throws.
   * Updates state to trigger the fallback render on the next cycle.
   *
   * @param error - The thrown error object.
   * @returns New state signalling an error has occurred.
   */
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  /**
   * Called after getDerivedStateFromError.
   * Use this for side effects (e.g., error reporting to Sentry).
   *
   * @param error - The thrown error.
   * @param info  - React component stack information.
   */
  componentDidCatch(error: Error, info: ErrorInfo): void {
    // TODO: integrate Sentry / error monitoring in production
    console.error("[AetherWeave] Uncaught error:", error, info.componentStack);
  }

  /** Resets error state, allowing the user to retry. */
  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (!hasError) return children;
    if (fallback) return fallback;

    return (
      <div className="min-h-dvh bg-void-950 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-card max-w-md w-full p-8 text-center space-y-6"
        >
          {/* Animated glitch icon */}
          <div className="text-6xl select-none animate-aether-pulse">⚠</div>

          <div className="space-y-2">
            <h1 className="text-xl font-display font-semibold text-foreground">
              Neural Loom Disruption
            </h1>
            <p className="text-sm text-muted-foreground">
              An unexpected error collapsed part of the weave.
            </p>
          </div>

          {/* Error details — visible in dev; redacted in prod */}
          {process.env.NODE_ENV === "development" && error && (
            <pre className="text-left text-xs bg-void-900 p-3 rounded-md text-mutagen-300 overflow-auto max-h-32">
              {error.message}
            </pre>
          )}

          <div className="flex gap-3 justify-center">
            <button
              onClick={this.handleReset}
              className="cyber-btn px-6"
            >
              Retry
            </button>
            <button
              onClick={() => window.location.reload()}
              className="cyber-btn px-6 border-synapse-400/50 text-synapse-200 hover:bg-synapse-500/20"
            >
              Reload Page
            </button>
          </div>
        </motion.div>
      </div>
    );
  }
}

/* ─── SectionErrorBoundary ───────────────────────────────────────────────── */

/**
 * SectionErrorBoundary — lightweight boundary for sidebar panels and canvas
 * overlays. Renders a compact inline error strip rather than a full-page halt.
 *
 * @param props.children - The UI section to protect.
 * @param props.fallback - Optional custom fallback.
 */
export class SectionErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[AetherWeave] Section error:", error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    const { hasError } = this.state;
    const { children, fallback } = this.props;

    if (!hasError) return children;
    if (fallback) return fallback;

    return (
      <div className="flex items-center justify-between gap-3 p-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
        <span>Section error — weave fragment offline.</span>
        <button
          onClick={this.handleReset}
          className="shrink-0 underline hover:no-underline text-xs"
        >
          Retry
        </button>
      </div>
    );
  }
}
