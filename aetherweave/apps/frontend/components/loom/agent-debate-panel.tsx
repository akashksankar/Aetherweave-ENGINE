/**
 * @fileoverview AgentDebatePanel — Live agent speech bubble feed
 *
 * Renders the real-time multi-agent debate as an animated chat-like feed.
 * Each agent (Architect, Critic, Futurist, Debater) has a distinct colour,
 * icon, and speech-bubble style. New messages slide in from the bottom.
 *
 * Also shows the Echo Agent debate transcript as a compact table
 * when debate_consensus data is available.
 *
 * @module components/loom/agent-debate-panel
 */

"use client";

import React, { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLoomStore } from "@/store/loom-store";
import type { AgentMessage } from "@aetherweave/shared";

/* ─── Agent theme config ─────────────────────────────────────────────────── */

interface AgentTheme {
  label: string;
  color: string;       // Tailwind text colour class
  bg: string;          // Tailwind bg class for the bubble
  border: string;      // border colour class
  emoji: string;
}

const AGENT_THEMES: Record<string, AgentTheme> = {
  architect: {
    label: "Architect",
    color: "text-aether-300",
    bg:    "bg-aether-950/60",
    border:"border-aether-800/50",
    emoji: "🏗️",
  },
  critic: {
    label: "Critic",
    color: "text-synapse-300",
    bg:    "bg-synapse-950/60",
    border:"border-synapse-800/50",
    emoji: "🔬",
  },
  futurist: {
    label: "Futurist",
    color: "text-mutagen-300",
    bg:    "bg-mutagen-950/60",
    border:"border-mutagen-800/50",
    emoji: "🔭",
  },
  debater: {
    label: "Debater",
    color: "text-violet-300",
    bg:    "bg-violet-950/60",
    border:"border-violet-800/50",
    emoji: "⚖️",
  },
};

const FALLBACK_THEME: AgentTheme = {
  label: "Agent",
  color: "text-void-300",
  bg:    "bg-void-900/60",
  border:"border-void-700/50",
  emoji: "🤖",
};

/* ─── Sub-components ─────────────────────────────────────────────────────── */

/**
 * SingleBubble — renders one agent message as an animated speech bubble.
 *
 * @param message - AgentMessage from the WS stream.
 * @param index   - Position in the list (used for stagger delay).
 */
function SingleBubble({
  message,
  index,
}: {
  message: AgentMessage;
  index: number;
}): React.JSX.Element {
  const theme = AGENT_THEMES[message.role] ?? FALLBACK_THEME;

  return (
    <motion.div
      key={`${message.role}-${message.generation}-${index}`}
      initial={{ opacity: 0, x: -12, scale: 0.97 }}
      animate={{ opacity: 1, x: 0,  scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.25, delay: index * 0.03 }}
      className={`
        rounded-lg border p-2.5 space-y-1
        ${theme.bg} ${theme.border}
      `}
    >
      {/* Header: emoji + role + confidence + gen badge */}
      <div className="flex items-center gap-2 justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">{theme.emoji}</span>
          <span className={`text-[11px] font-semibold font-mono uppercase tracking-wider ${theme.color}`}>
            {theme.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-mono text-void-500">
            G{message.generation}
          </span>
          <span
            className="text-[9px] font-mono px-1 rounded"
            style={{
              background: `rgba(167,139,250,${message.confidence * 0.3})`,
              color: "#a78bfa",
            }}
          >
            {(message.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Message content */}
      <p className="text-[11px] text-void-300 leading-relaxed font-mono line-clamp-4">
        {message.content}
      </p>
    </motion.div>
  );
}

/* ─── Main component ─────────────────────────────────────────────────────── */

/**
 * AgentDebatePanel component.
 *
 * Displays:
 * 1. A scrolling feed of all agent speech bubbles received so far.
 * 2. The latest Echo Agent debate transcript (round/stance/vote table).
 * 3. A consensus indicator (✅ or ⚠️).
 *
 * Auto-scrolls to the latest message when new ones arrive.
 *
 * @returns JSX element.
 */
export function AgentDebatePanel(): React.JSX.Element {
  const agentMessages  = useLoomStore((s) => s.agentMessages);
  const agentDebate    = useLoomStore((s) => s.agentDebate);
  const scrollRef      = useRef<HTMLDivElement>(null);

  /** Auto-scroll to the bottom when new messages arrive. */
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [agentMessages.length]);

  const empty = agentMessages.length === 0;

  const VOTE_COLORS: Record<string, string> = {
    ACCEPT: "text-emerald-400",
    REJECT: "text-red-400",
    MODIFY: "text-amber-400",
  };

  return (
    <div className="w-full flex flex-col gap-3">
      {/* ── Speech bubble feed ──────────────────────────────────────────── */}
      <div
        ref={scrollRef}
        className="
          flex flex-col gap-2 overflow-y-auto pr-1
          max-h-[320px] scrollbar-thin
          scrollbar-thumb-void-700 scrollbar-track-transparent
        "
      >
        {empty ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8">
            <span className="text-3xl opacity-30">🧬</span>
            <span className="text-[11px] font-mono text-void-600 italic text-center">
              Agent swarm awaiting activation.
              <br />Start evolution to see the debate.
            </span>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {agentMessages.slice(-20).map((msg, i) => (
              <SingleBubble
                key={`${msg.role}-${msg.generation}-${i}`}
                message={msg}
                index={i}
              />
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* ── Echo Debate transcript (latest generation only) ─────────────── */}
      {agentDebate && agentDebate.transcript.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-void-800 bg-void-950 p-3 space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-void-400 uppercase tracking-widest">
              Echo Debate
            </span>
            <span
              className={`text-[10px] font-mono ${
                agentDebate.consensus ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {agentDebate.consensus ? "✅ Consensus" : "⚠️ Contested"}
            </span>
          </div>

          {/* Transcript table: only round-2 votes */}
          <div className="space-y-1">
            {agentDebate.transcript
              .filter((t) => t.round === 2)
              .map((t, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span
                    className={`text-[10px] font-mono font-bold w-20 shrink-0 ${
                      t.stance === "OPTIMIST"
                        ? "text-emerald-400"
                        : t.stance === "PESSIMIST"
                          ? "text-red-400"
                          : "text-amber-400"
                    }`}
                  >
                    {t.stance}
                  </span>
                  <span className="text-[10px] font-mono text-void-400 line-clamp-2 flex-1">
                    {t.content}
                  </span>
                  {t.vote && (
                    <span
                      className={`text-[10px] font-mono font-bold shrink-0 ${
                        VOTE_COLORS[t.vote] ?? "text-void-300"
                      }`}
                    >
                      {t.vote}
                    </span>
                  )}
                </div>
              ))}
          </div>

          {/* Score summary */}
          <div className="flex gap-4 pt-1 border-t border-void-800">
            <span className="text-[10px] font-mono text-void-500">
              Critic:{" "}
              <span className="text-synapse-400">
                {(agentDebate.criticScore * 100).toFixed(0)}%
              </span>
            </span>
            <span className="text-[10px] font-mono text-void-500">
              Futurist:{" "}
              <span className="text-mutagen-400">
                {(agentDebate.futuristScore * 100).toFixed(0)}%
              </span>
            </span>
          </div>
        </motion.div>
      )}
    </div>
  );
}
