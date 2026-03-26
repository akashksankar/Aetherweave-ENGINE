"use client";

/**
 * @fileoverview useToast — Toast state management hook
 *
 * Provides a global queue of toasts that the `<Toaster>` component renders.
 * Uses a module-level reducer pattern (no React context needed) for simplicity.
 *
 * @module hooks/use-toast
 */

import * as React from "react";
import type { ToastActionElement, ToastProps } from "@/components/ui/toast";

/* ─── Types ──────────────────────────────────────────────────────────────── */

const TOAST_LIMIT = 5;
const TOAST_REMOVE_DELAY = 4000; // ms before dismissed toast is removed from DOM

type ToasterToast = ToastProps & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: ToastActionElement;
};

const actionTypes = {
  ADD_TOAST:    "ADD_TOAST",
  UPDATE_TOAST: "UPDATE_TOAST",
  DISMISS_TOAST: "DISMISS_TOAST",
  REMOVE_TOAST: "REMOVE_TOAST",
} as const;

type Action =
  | { type: "ADD_TOAST";     toast: ToasterToast }
  | { type: "UPDATE_TOAST";  toast: Partial<ToasterToast> }
  | { type: "DISMISS_TOAST"; toastId?: string }
  | { type: "REMOVE_TOAST";  toastId?: string };

interface State { toasts: ToasterToast[] }

/* ─── Module-level state (avoids Context overhead) ───────────────────────── */

let count = 0;
const genId = () => `toast-${(count++).toString(36)}`;

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();
const listeners: Array<(state: State) => void> = [];
let memoryState: State = { toasts: [] };

function dispatch(action: Action) {
  memoryState = reducer(memoryState, action);
  listeners.forEach((l) => l(memoryState));
}

/* ─── Reducer ────────────────────────────────────────────────────────────── */

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_TOAST":
      return {
        ...state,
        toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
      };
    case "UPDATE_TOAST":
      return {
        ...state,
        toasts: state.toasts.map((t) =>
          t.id === action.toast.id ? { ...t, ...action.toast } : t
        ),
      };
    case "DISMISS_TOAST": {
      const { toastId } = action;
      if (toastId) {
        scheduleRemove(toastId);
      } else {
        state.toasts.forEach((t) => scheduleRemove(t.id));
      }
      return {
        ...state,
        toasts: state.toasts.map((t) =>
          !toastId || t.id === toastId ? { ...t, open: false } : t
        ),
      };
    }
    case "REMOVE_TOAST":
      return {
        ...state,
        toasts: action.toastId
          ? state.toasts.filter((t) => t.id !== action.toastId)
          : [],
      };
  }
}

function scheduleRemove(toastId: string) {
  if (toastTimeouts.has(toastId)) return;
  const timeout = setTimeout(() => {
    toastTimeouts.delete(toastId);
    dispatch({ type: "REMOVE_TOAST", toastId });
  }, TOAST_REMOVE_DELAY);
  toastTimeouts.set(toastId, timeout);
}

/* ─── Public API ─────────────────────────────────────────────────────────── */

/**
 * toast() — imperative toast creator.
 *
 * @param props - Toast configuration.
 * @returns Object with id, update, and dismiss methods.
 */
function toast(props: Omit<ToasterToast, "id">) {
  const id = genId();

  const update   = (p: Partial<ToasterToast>) => dispatch({ type: "UPDATE_TOAST",  toast: { ...p, id } });
  const dismiss  = ()                          => dispatch({ type: "DISMISS_TOAST", toastId: id });

  dispatch({
    type: "ADD_TOAST",
    toast: { ...props, id, open: true, onOpenChange: (open) => { if (!open) dismiss(); } },
  });

  return { id, update, dismiss };
}

/**
 * useToast — React hook for subscribing to the global toast queue.
 *
 * @returns { toasts, toast, dismiss } — current list and action creators.
 */
function useToast() {
  const [state, setState] = React.useState<State>(memoryState);

  React.useEffect(() => {
    listeners.push(setState);
    return () => {
      const idx = listeners.indexOf(setState);
      if (idx > -1) listeners.splice(idx, 1);
    };
  }, []);

  return {
    toasts: state.toasts,
    toast,
    dismiss: (toastId?: string) => dispatch({ type: "DISMISS_TOAST", toastId }),
  };
}

export { useToast, toast };
