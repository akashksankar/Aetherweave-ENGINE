/**
 * @fileoverview useEvolution — WebSocket evolution streaming hook
 *
 * Opens a WebSocket connection to /ws/evolution and dispatches
 * all incoming events to the Zustand store.
 *
 * Usage:
 *   const { connect, disconnect, isConnected } = useEvolution();
 *   // Call connect() when user clicks "Evolve"
 *
 * @module hooks/use-evolution
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLoomStore } from "@/store/loom-store";

/** WebSocket endpoint URL (same origin, dev proxied by Next.js). */
const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL?.replace(/^http/, "ws") ??
  "ws://localhost:8000";

const WS_ENDPOINT = `${WS_URL}/ws/evolution`;

/** Internal connection state (separate from evolutionStatus in the store). */
type ConnectionState = "disconnected" | "connecting" | "open" | "closed";

interface UseEvolutionReturn {
  /** Connect and start an evolution run. */
  connect: () => void;
  /** Disconnect from the WebSocket. */
  disconnect: () => void;
  /** True while the WebSocket readyState === OPEN. */
  isConnected: boolean;
  /** Low-level connection state string. */
  connectionState: ConnectionState;
}

/**
 * useEvolution — manages the WebSocket lifecycle for an evolution run.
 *
 * Opens, reads, and closes a WebSocket to the FastAPI /ws/evolution endpoint.
 * All incoming JSON messages are dispatched to the Zustand loom-store:
 *   - type "generation" → onGenerationEvent()
 *   - type "complete"   → onEvolutionComplete()
 *   - type "error"      → onEvolutionError()
 *
 * The hook automatically reconnects (up to 3 times) on unexpected closure
 * with an exponential back-off of 1s, 2s, 4s.
 *
 * @returns An object with connect(), disconnect(), isConnected, connectionState.
 */
export function useEvolution(): UseEvolutionReturn {
  const wsRef      = useRef<WebSocket | null>(null);
  const retryRef   = useRef<number>(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");

  const {
    intent,
    evolutionConfig,
    activeGraphId,
    startEvolution,
    onEvolutionConnected,
    onGenerationEvent,
    onEvolutionComplete,
    onEvolutionError,
  } = useLoomStore();

  /**
   * Tear down the current WebSocket connection cleanly.
   * Cancels any pending retry timers.
   */
  const disconnect = useCallback(() => {
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent retry on manual disconnect
      wsRef.current.close(1000, "User closed");
      wsRef.current = null;
    }
    retryRef.current = 0;
    setConnectionState("closed");
  }, []);

  /**
   * Open a new WebSocket connection and wire up all event handlers.
   *
   * Sends the evolution config as the first message after the connection
   * is established (the backend expects this before starting the loop).
   */
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    startEvolution();
    setConnectionState("connecting");

    const ws = new WebSocket(WS_ENDPOINT);
    wsRef.current = ws;

    /** Send config immediately on connection open. */
    ws.onopen = () => {
      setConnectionState("open");
      onEvolutionConnected();
      retryRef.current = 0;

      const config = {
        architectureId: activeGraphId ?? "demo",
        generations:    evolutionConfig.generations,
        populationSize: evolutionConfig.populationSize,
        intent:         intent || "Evolving architecture",
        enableDebate:   evolutionConfig.enableDebate,
      };
      ws.send(JSON.stringify(config));
    };

    /** Dispatch parsed events to the Zustand store. */
    ws.onmessage = (ev: MessageEvent) => {
      try {
        const event = JSON.parse(ev.data as string);

        switch (event.type) {
          case "generation":
            onGenerationEvent({
              generation:  event.generation,
              graph:       event.graph,
              fitness:     event.fitness,
              agentDebate: event.agentDebate ?? null,
            });
            break;

          case "complete":
            onEvolutionComplete({
              bestGraph:      event.result.bestGraph,
              fitnessHistory: event.result.fitnessHistory,
            });
            setConnectionState("closed");
            break;

          case "error":
            onEvolutionError(event.message ?? "Unknown WebSocket error");
            setConnectionState("closed");
            break;

          default:
            break;
        }
      } catch {
        // Malformed JSON — log silently and continue
        console.warn("[useEvolution] Failed to parse WS message:", ev.data);
      }
    };

    /**
     * Auto-retry logic: on unexpected close (code !== 1000),
     * reconnect up to 3 times with exponential backoff.
     */
    ws.onclose = (ev: CloseEvent) => {
      setConnectionState("disconnected");
      if (ev.code === 1000 || retryRef.current >= 3) return;

      const delay = Math.pow(2, retryRef.current) * 1000;
      retryRef.current++;
      console.info(
        `[useEvolution] Reconnecting in ${delay}ms (attempt ${retryRef.current}/3)`
      );
      retryTimer.current = setTimeout(() => connect(), delay);
    };

    ws.onerror = () => {
      onEvolutionError("WebSocket connection failed. Is the backend running?");
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intent, evolutionConfig, activeGraphId]);

  /** Clean up on unmount. */
  useEffect(() => {
    return () => disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    connect,
    disconnect,
    isConnected:     connectionState === "open",
    connectionState,
  };
}
