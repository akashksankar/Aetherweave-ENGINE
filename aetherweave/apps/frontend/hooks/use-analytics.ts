/**
 * @fileoverview useAnalytics — TanStack Query hooks for Neo4j analytics
 *
 * Fetches graph analytics and Pareto front data from the backend.
 *
 * @module hooks/use-analytics
 */

"use client";

import { useQuery } from "@tanstack/react-query";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<T>;
}

/* ─── Shared types ───────────────────────────────────────────────────────── */

export interface AnalyticsBottleneck {
  node_id:    string;
  label:      string;
  node_type:  string;
  path_count: number;
  severity:   number;
}

export interface AnalyticsCluster {
  cluster_id:  number;
  node_ids:    string[];
  size:        number;
  is_isolated: boolean;
}

export interface AnalyticsCriticalPath {
  node_ids:     string[];
  total_weight: number;
  hops:         number;
  is_long:      boolean;
}

export interface AnalyticsHub {
  node_id:     string;
  label:       string;
  node_type:   string;
  degree:      number;
  mean_degree: number;
}

export interface AnalyticsResult {
  graph_id:         string;
  bottlenecks:      AnalyticsBottleneck[];
  clusters:         AnalyticsCluster[];
  critical_path:    AnalyticsCriticalPath | null;
  hubs:             AnalyticsHub[];
  resilience_score: number;
  cluster_count:    number;
  bottleneck_count: number;
}

export interface ParetoIndividual {
  rank:             number;
  scalability:      number;
  cost_efficiency:  number;
  future_proof:     number;
  aggregate:        number;
  generation:       number;
  node_count:       number;
}

export interface ParetoFrontResult {
  graph_id:    string;
  individuals: ParetoIndividual[];
  front_size:  number;
  dominated:   number;
}

/* ─── Hooks ──────────────────────────────────────────────────────────────── */

/**
 * Fetch (and auto-refresh) Neo4j analytics for the active graph.
 * Refetches every 60s to stay in sync with the 60s Redis TTL.
 *
 * @param graphId - Architecture UUID string. Pass null to disable.
 */
export function useAnalytics(graphId: string | null) {
  return useQuery<AnalyticsResult>({
    queryKey:        ["analytics", graphId],
    queryFn:         () => apiFetch<AnalyticsResult>(`/api/v1/analytics/${graphId}`),
    enabled:         !!graphId,
    refetchInterval: 60_000,
    staleTime:       55_000,
    retry:           1,
  });
}

/**
 * Fetch Pareto front data for the active graph.
 * Refreshed after each evolution complete event (invalidated by the store).
 *
 * @param graphId - Architecture UUID string. Pass null to disable.
 */
export function useParetoFront(graphId: string | null) {
  return useQuery<ParetoFrontResult>({
    queryKey:  ["pareto", graphId],
    queryFn:   () => apiFetch<ParetoFrontResult>(`/api/v1/analytics/${graphId}/pareto`),
    enabled:   !!graphId,
    staleTime: 30_000,
    retry:     1,
  });
}
