"use client";

/**
 * @fileoverview Global Providers — AetherWeave Frontend
 *
 * Wraps the entire application with:
 * 1. `QueryClientProvider` — TanStack React Query for server-state management.
 * 2. `ReactQueryDevtools` — dev-mode query inspector (tree-shaken in production).
 *
 * Why a separate Providers file?
 * Next.js 15 App Router requires all context providers that use hooks
 * (like React Query) to live inside Client Components. By isolating them here,
 * the root layout can remain a Server Component.
 *
 * @module components/providers
 */

import React, { useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  isServer,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

/* ─── QueryClient factory ─────────────────────────────────────────────────── */

/**
 * Creates a new QueryClient instance with sensible defaults for AetherWeave.
 *
 * Key settings:
 * - `staleTime: 30_000` — evolutionary data is considered fresh for 30 s.
 * - `retry: 3` — auto-retry failed network requests up to 3 times.
 * - `refetchOnWindowFocus: false` — avoids intrusive refetches in the 3D canvas.
 *
 * @returns A configured QueryClient instance.
 */
function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,                   // 30 s
        retry: 3,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 1,
      },
    },
  });
}

/** Singleton QueryClient for the browser context. */
let browserQueryClient: QueryClient | undefined;

/**
 * Returns the browser-singleton QueryClient.
 * On the server a new instance is created per-request to avoid shared state.
 *
 * @returns QueryClient instance appropriate for the current context.
 */
function getQueryClient(): QueryClient {
  if (isServer) {
    // Server: always create a fresh client (SSR safety)
    return makeQueryClient();
  }
  // Browser: use the singleton (preserves cache across navigations)
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient();
  }
  return browserQueryClient;
}

/* ─── Providers Component ─────────────────────────────────────────────────── */

/**
 * Providers — root context provider tree for AetherWeave.
 *
 * @param props.children - The page content to wrap.
 * @returns Context-wrapped children ready for data-fetching and global state.
 *
 * Responsiveness note:
 * This component has no visual output and therefore no responsive concerns.
 * All layout responsiveness is handled inside the page and sidebar components.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  /**
   * `useState` ensures a stable QueryClient reference that doesn't reset
   * on every render, while still being created on the client side.
   * This pattern is recommended by TanStack for Next.js App Router.
   */
  const [queryClient] = useState(() => getQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* ReactQueryDevtools only renders in development — safe to keep here */}
      <ReactQueryDevtools
        initialIsOpen={false}
        position="bottom"
        buttonPosition="bottom-right"
      />
    </QueryClientProvider>
  );
}
