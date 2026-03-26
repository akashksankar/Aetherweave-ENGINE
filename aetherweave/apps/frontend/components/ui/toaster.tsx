"use client";

/**
 * @fileoverview Toaster — shadcn/ui Toast Renderer
 *
 * Renders all active toasts from the `useToast` hook into a fixed portal.
 * Positioned at the bottom-right on desktop and bottom-center on mobile.
 *
 * @module components/ui/toaster
 */

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";

/**
 * Toaster — mounts the Radix Toast portal.
 * Drop this once inside the root layout; it will render all toasts application-wide.
 *
 * @returns Radix ToastProvider with all active toasts rendered.
 */
export function Toaster() {
  const { toasts } = useToast();

  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, action, ...props }) => (
        <Toast key={id} {...props}>
          <div className="grid gap-1">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && <ToastDescription>{description}</ToastDescription>}
          </div>
          {action}
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}
