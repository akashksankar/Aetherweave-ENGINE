import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * cn — Tailwind class merger utility.
 *
 * Combines `clsx` (for conditional class logic) with `tailwind-merge`
 * (for deduplicating conflicting Tailwind utilities).
 *
 * @example
 * cn("px-4 py-2", condition && "bg-blue-500", "py-3")
 * // → "px-4 bg-blue-500 py-3" (py-2 overridden by py-3)
 *
 * @param inputs - Any mix of string, array, or conditional class values.
 * @returns A single merged + deduped class string.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * formatNumber — compact number formatting for fitness scores and counts.
 *
 * @param n      - The raw number.
 * @param digits - Decimal places (default 2).
 * @returns Formatted string, e.g. "0.87" or "1.2k".
 */
export function formatNumber(n: number, digits = 2): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return n.toFixed(digits);
}

/**
 * clamp — constrains a value within [min, max].
 *
 * @param value - Input value.
 * @param min   - Lower bound.
 * @param max   - Upper bound.
 * @returns Clamped value.
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * sleep — promise-based delay (useful in async generators / tests).
 *
 * @param ms - Milliseconds to wait.
 * @returns Promise that resolves after `ms` milliseconds.
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * nodeTypeColor — returns the Tailwind text colour class for a node type.
 * Keeps colours consistent between the sidebar badges and the 3D canvas.
 *
 * @param type - NodeType string literal.
 * @returns Tailwind text colour class string.
 */
export function nodeTypeColor(type: string): string {
  const map: Record<string, string> = {
    service:  "text-aether-400",
    database: "text-mutagen-300",
    gateway:  "text-synapse-300",
    cache:    "text-green-400",
    queue:    "text-orange-400",
    cdn:      "text-blue-400",
    auth:     "text-pink-400",
    monitor:  "text-yellow-400",
    ml:       "text-purple-400",
    edge:     "text-cyan-400",
  };
  return map[type] ?? "text-foreground";
}

/**
 * nodeTypeHex — maps a NodeType to a hex colour for Three.js materials.
 *
 * @param type - NodeType string literal.
 * @returns Hex colour string.
 */
export function nodeTypeHex(type: string): string {
  const map: Record<string, string> = {
    service:  "#22d3ee",
    database: "#fbbf24",
    gateway:  "#c4b5fd",
    cache:    "#4ade80",
    queue:    "#fb923c",
    cdn:      "#60a5fa",
    auth:     "#f472b6",
    monitor:  "#facc15",
    ml:       "#a78bfa",
    edge:     "#67e8f9",
  };
  return map[type] ?? "#ffffff";
}
