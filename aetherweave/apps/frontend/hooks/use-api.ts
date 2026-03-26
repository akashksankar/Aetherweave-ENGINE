/**
 * @fileoverview API hooks — TanStack Query hooks for AetherWeave REST endpoints.
 *
 * Wraps the FastAPI backend with type-safe React Query hooks:
 *   - useSystemStatus   → GET /api/v1/status  (polling every 30s)
 *   - useArchitectures  → GET /api/v1/architecture (paginated list)
 *   - useArchitecture   → GET /api/v1/architecture/{id}
 *   - useCreateArch     → POST /api/v1/architecture/create (mutation)
 *
 * All hooks read the base URL from NEXT_PUBLIC_API_URL (defaults to localhost:8000).
 *
 * @module hooks/use-api
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ArchGraph, SystemStatus } from "@aetherweave/shared";

/* ─── API base URL ───────────────────────────────────────────────────────── */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/* ─── Fetch helper ───────────────────────────────────────────────────────── */

/**
 * Typed fetch wrapper that throws on HTTP errors.
 *
 * @param path - URL path relative to API_BASE.
 * @param init - Optional RequestInit for method, body, headers.
 * @returns Parsed JSON as generic type T.
 * @throws Error with response status message on non-2xx responses.
 */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ─── Query keys ─────────────────────────────────────────────────────────── */

export const queryKeys = {
  status:       ["system-status"] as const,
  architectures: (limit?: number, offset?: number) =>
    ["architectures", limit, offset] as const,
  architecture: (id: string) => ["architecture", id] as const,
} as const;

/* ─── useSystemStatus ────────────────────────────────────────────────────── */

/**
 * Polls GET /api/v1/status every 30 seconds to check service health.
 *
 * Returns the raw SystemStatus payload which is used by the StatusBar
 * component to show per-service indicators (PostgreSQL, Neo4j, Redis, Celery).
 *
 * @returns TanStack Query result containing SystemStatus | undefined.
 */
export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: queryKeys.status,
    queryFn:  () => apiFetch<SystemStatus>("/api/v1/status"),
    refetchInterval: 30_000,  // Poll every 30 s
    retry: 1,
    staleTime: 25_000,
  });
}

/* ─── useArchitectures ───────────────────────────────────────────────────── */

interface ArchListItem {
  id:         string;
  name:       string;
  generation: number;
  fitness:    { aggregate: number };
  nodeCount:  number;
  isEvolving: boolean;
  createdAt:  string;
}

interface ArchListResponse {
  total: number;
  items: ArchListItem[];
}

/**
 * Fetches the paginated list of architecture graphs.
 *
 * @param limit  - Max items per page (default 20).
 * @param offset - Number of items to skip (default 0).
 * @returns TanStack Query result with { total, items }.
 */
export function useArchitectures(limit = 20, offset = 0) {
  return useQuery<ArchListResponse>({
    queryKey: queryKeys.architectures(limit, offset),
    queryFn: () =>
      apiFetch<ArchListResponse>(
        `/api/v1/architecture?limit=${limit}&offset=${offset}`
      ),
    staleTime: 10_000,
  });
}

/* ─── useArchitecture ────────────────────────────────────────────────────── */

/**
 * Fetches one architecture graph by ID.
 *
 * @param id - UUID of the graph to fetch.
 * @returns TanStack Query result with ArchGraph | undefined.
 */
export function useArchitecture(id: string | null) {
  return useQuery<ArchGraph>({
    queryKey: queryKeys.architecture(id ?? ""),
    queryFn: () => apiFetch<ArchGraph>(`/api/v1/architecture/${id}`),
    enabled: !!id,
    staleTime: 5_000,
  });
}

/* ─── useCreateArchitecture ──────────────────────────────────────────────── */

interface CreateArchRequest {
  intent:       string;
  initial_nodes?: number;
  seed?:        number;
}

/**
 * Mutation hook for POST /architecture/create.
 *
 * On success, invalidates the architectures list cache so the sidebar
 * history automatically refreshes.
 *
 * @returns TanStack Mutation with mutateAsync(body: CreateArchRequest).
 */
export function useCreateArchitecture() {
  const qc = useQueryClient();

  return useMutation<ArchGraph, Error, CreateArchRequest>({
    mutationFn: (body) =>
      apiFetch<ArchGraph>("/api/v1/architecture/create", {
        method: "POST",
        body:   JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.architectures() });
    },
  });
}

/* ─── useStartEvolution ──────────────────────────────────────────────────── */

interface StartEvolveRequest {
  architecture_id: string;
  generations:     number;
  population_size: number;
  enable_debate?:  boolean;
}

interface StartEvolveResponse {
  run_id:          string;
  architecture_id: string;
  status:          "queued";
  generations:     number;
}

/**
 * Mutation hook for POST /api/v1/evolve.
 * Queues the evolution run. Real-time progress is streamed via WebSocket.
 *
 * @returns TanStack Mutation that returns StartEvolveResponse.
 */
export function useStartEvolution() {
  return useMutation<StartEvolveResponse, Error, StartEvolveRequest>({
    mutationFn: (body) =>
      apiFetch<StartEvolveResponse>("/api/v1/evolve", {
        method: "POST",
        body:   JSON.stringify(body),
      }),
  });
}
