/**
 * @fileoverview SymbiosisPanel — DNA sharing QR code generator
 *
 * Allows users to share their evolved architecture as a "symbiosis token"
 * — a one-time link encoded as a QR code that another user can scan to
 * import the architecture's DNA into their own loom.
 *
 * Flow:
 *   1. User clicks "Share Architecture DNA"
 *   2. Frontend calls POST /api/v1/architecture/{id}/symbiosis/create
 *   3. Backend creates a SymbiosisToken with an expiry (1h default)
 *   4. Token URL is encoded into a QR code (via qrcode.react)
 *   5. User shares QR code or copies link
 *   6. Recipient scans and visits the link → loads the shared architecture
 *
 * Also shows:
 *   - Expiry countdown timer
 *   - Architecture fitness summary
 *   - Prominent "Revoke Token" button
 *
 * @module components/loom/symbiosis-panel
 */

"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { motion, AnimatePresence } from "framer-motion";
import { useLoomStore } from "@/store/loom-store";
import { useToast } from "@/hooks/use-toast";

/* ─── API helpers ────────────────────────────────────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const APP_BASE = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

interface SymbiosisToken {
  token:      string;
  expiresAt:  string;
  shareUrl:   string;
}

/**
 * POST /api/v1/architecture/{id}/symbiosis/create
 * Creates a new symbiosis token and returns the share URL.
 */
async function createSymbiosisToken(
  archId:     string,
  expiryHours: number
): Promise<SymbiosisToken> {
  const res = await fetch(
    `${API_BASE}/api/v1/architecture/${archId}/symbiosis/create`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expiry_hours: expiryHours }),
    }
  );
  if (!res.ok) throw new Error(`Token creation failed: ${res.status}`);
  const data = await res.json();
  return {
    token:     data.token,
    expiresAt: data.expires_at,
    shareUrl:  `${APP_BASE}/join?token=${data.token}`,
  };
}

/**
 * DELETE /api/v1/architecture/{id}/symbiosis/{token}
 * Revokes (marks as used) a symbiosis token.
 */
async function revokeSymbiosisToken(
  archId: string,
  token:  string
): Promise<void> {
  await fetch(
    `${API_BASE}/api/v1/architecture/${archId}/symbiosis/${token}`,
    { method: "DELETE" }
  );
}

/* ─── Countdown timer ────────────────────────────────────────────────────── */

/**
 * useCountdown — ticks down every second, returns remaining seconds.
 *
 * @param expiresAt ISO timestamp string of expiry.
 * @returns Remaining seconds (0 if expired).
 */
function useCountdown(expiresAt: string | null): number {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!expiresAt) { setRemaining(0); return; }

    const target = new Date(expiresAt).getTime();

    const tick = () => {
      const diff = Math.max(0, Math.floor((target - Date.now()) / 1000));
      setRemaining(diff);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  return remaining;
}

/** Format seconds as MM:SS. */
function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

/* ─── Main component ─────────────────────────────────────────────────────── */

/** Expiry options in hours. */
const EXPIRY_OPTIONS = [
  { label: "15 min",  hours: 0.25 },
  { label: "1 hour",  hours: 1    },
  { label: "24 hours", hours: 24   },
  { label: "7 days",  hours: 168  },
];

/**
 * SymbiosisPanel — architecture DNA QR code share panel.
 *
 * Shown in the sidebar when the user has an active graph.
 * Generates a one-time QR code that another user can scan to import
 * the current architecture's DNA into their own loom instance.
 *
 * @returns JSX element.
 */
export function SymbiosisPanel(): React.JSX.Element {
  const activeGraphId  = useLoomStore((s) => s.activeGraphId);
  const latestFitness  = useLoomStore((s) => s.latestFitness);
  const activeGraph    = useLoomStore((s) => s.activeGraph);

  const [token,       setToken]       = useState<SymbiosisToken | null>(null);
  const [loading,     setLoading]     = useState(false);
  const [expiryHours, setExpiryHours] = useState(1);
  const [copied,      setCopied]      = useState(false);
  const { toast } = useToast();

  const remaining = useCountdown(token?.expiresAt ?? null);
  const expired = token !== null && remaining === 0;

  /** Generate a new symbiosis token. */
  const handleGenerate = useCallback(async () => {
    if (!activeGraphId) {
      toast({ title: "No active graph", description: "Create an architecture first.", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const t = await createSymbiosisToken(activeGraphId, expiryHours);
      setToken(t);
      toast({ title: "✦ Symbiosis token created", description: "Share the QR code or link below." });
    } catch (err) {
      toast({ title: "Token creation failed", description: (err as Error).message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [activeGraphId, expiryHours, toast]);

  /** Revoke the current token. */
  const handleRevoke = useCallback(async () => {
    if (!token || !activeGraphId) return;
    try {
      await revokeSymbiosisToken(activeGraphId, token.token);
      setToken(null);
      toast({ title: "Token revoked" });
    } catch {
      toast({ title: "Revoke failed", variant: "destructive" });
    }
  }, [token, activeGraphId, toast]);

  /** Copy share URL to clipboard. */
  const handleCopy = useCallback(async () => {
    if (!token) return;
    await navigator.clipboard.writeText(token.shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [token]);

  const hasGraph = !!activeGraphId;

  return (
    <div className="w-full space-y-4">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div>
        <h3 className="text-[11px] font-mono font-semibold text-void-300 uppercase tracking-widest">
          🧬 Symbiosis DNA Share
        </h3>
        <p className="text-[10px] font-mono text-void-600 mt-1">
          Generate a scannable QR code to share your evolved architecture&apos;s
          genetic blueprint with another AetherWeave instance.
        </p>
      </div>

      {/* ── Fitness summary strip ────────────────────────────────────────── */}
      {latestFitness && (
        <div className="flex gap-2 flex-wrap">
          {[
            { label: "Scale", value: latestFitness.scalability,    color: "#34d399" },
            { label: "Cost",  value: latestFitness.costEfficiency, color: "#fb923c" },
            { label: "Future",value: latestFitness.futureProof,    color: "#38bdf8" },
            { label: "∑",     value: latestFitness.aggregate,      color: "#a78bfa" },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="flex-1 min-w-[52px] rounded-lg px-2 py-1.5 bg-void-900/60 border border-void-800/40 text-center"
            >
              <div
                className="text-[13px] font-mono font-bold tabular-nums"
                style={{ color }}
              >
                {(value * 100).toFixed(0)}
              </div>
              <div className="text-[9px] font-mono text-void-600">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── No graph warning ─────────────────────────────────────────────── */}
      {!hasGraph && (
        <div className="text-[11px] font-mono text-void-500 italic text-center py-3">
          Create an architecture first to enable sharing.
        </div>
      )}

      {/* ── Expiry selector ──────────────────────────────────────────────── */}
      {hasGraph && !token && (
        <div className="space-y-2">
          <span className="text-[10px] font-mono text-void-500 uppercase tracking-widest">
            Token Expiry
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            {EXPIRY_OPTIONS.map(({ label, hours }) => (
              <button
                key={hours}
                onClick={() => setExpiryHours(hours)}
                className={`
                  py-1.5 rounded-lg text-[11px] font-mono font-semibold border
                  transition-all duration-150
                  focus-visible:ring-1 focus-visible:ring-aether-500
                  ${expiryHours === hours
                    ? "bg-aether-900/60 border-aether-600 text-aether-300"
                    : "bg-void-900/40 border-void-800 text-void-500 hover:border-void-600"}
                `}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Generate button ───────────────────────────────────────────────── */}
      {hasGraph && !token && (
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="
            w-full py-2.5 rounded-xl text-[12px] font-mono font-bold
            border border-aether-700 text-aether-300
            bg-aether-950/50 hover:bg-aether-900/60
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-all duration-200
            focus-visible:ring-1 focus-visible:ring-aether-500
            shadow-[0_0_16px_rgba(139,92,246,0.1)] hover:shadow-[0_0_24px_rgba(139,92,246,0.25)]
          "
        >
          {loading ? "Generating…" : "✦ Generate Symbiosis QR Code"}
        </button>
      )}

      {/* ── QR code + share UI ───────────────────────────────────────────── */}
      <AnimatePresence>
        {token && !expired && (
          <motion.div
            key="qr-panel"
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.25 }}
            className="space-y-3"
          >
            {/* QR Code */}
            <div className="flex justify-center">
              <div className="p-3 rounded-xl bg-white shadow-lg shadow-aether-900/20">
                <QRCodeSVG
                  value={token.shareUrl}
                  size={180}
                  bgColor="#ffffff"
                  fgColor="#0a0118"
                  level="M"
                  includeMargin={false}
                />
              </div>
            </div>

            {/* Countdown */}
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] font-mono text-void-500">
                Expires in
              </span>
              <span
                className={`text-[13px] font-mono font-bold tabular-nums ${
                  remaining < 120 ? "text-red-400 animate-pulse" : "text-emerald-400"
                }`}
              >
                {formatCountdown(remaining)}
              </span>
            </div>

            {/* Share link input */}
            <div className="flex gap-2">
              <input
                readOnly
                value={token.shareUrl}
                className="
                  flex-1 min-w-0 rounded-lg px-2 py-1.5
                  bg-void-900/60 border border-void-800
                  text-[10px] font-mono text-void-400
                  focus:outline-none
                "
              />
              <button
                onClick={handleCopy}
                className="
                  px-3 py-1.5 rounded-lg text-[11px] font-mono
                  border border-void-700 text-void-300
                  bg-void-900 hover:bg-void-800
                  transition-colors duration-150 shrink-0
                "
              >
                {copied ? "✓" : "Copy"}
              </button>
            </div>

            {/* Token info strip */}
            <div className="rounded-lg px-3 py-2 bg-void-900/40 border border-void-800/40">
              <p className="text-[10px] font-mono text-void-500 leading-relaxed">
                Token: <span className="text-void-400 font-semibold">{token.token.slice(0, 8)}…</span>
                &nbsp;·&nbsp;Single-use &amp; encrypted.
                Recipient will receive a full copy of the architecture DNA.
              </p>
            </div>

            {/* Revoke button */}
            <button
              onClick={handleRevoke}
              className="
                w-full py-2 rounded-lg text-[11px] font-mono
                border border-red-900/60 text-red-400
                bg-red-950/20 hover:bg-red-950/40
                transition-all duration-150
                focus-visible:ring-1 focus-visible:ring-red-500
              "
            >
              Revoke Token
            </button>
          </motion.div>
        )}

        {/* Expired state */}
        {token && expired && (
          <motion.div
            key="expired"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center space-y-2 py-4"
          >
            <span className="text-3xl">⌛</span>
            <p className="text-[11px] font-mono text-void-500">
              Token expired.
            </p>
            <button
              onClick={() => { setToken(null); }}
              className="text-[11px] font-mono text-aether-400 hover:underline"
            >
              Generate a new one
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
