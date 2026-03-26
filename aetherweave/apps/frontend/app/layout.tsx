/**
 * @fileoverview AetherWeave Root Layout — Next.js 15 App Router
 *
 * This is the top-level Server Component that wraps every route.
 *
 * Responsibilities:
 * 1. Configures document <head> including fonts, viewport meta, and PWA tags.
 * 2. Provides global Providers (QueryClient, TanStack Query DevTools).
 * 3. Renders the global ErrorBoundary.
 * 4. Applies dark theme CSS class to <html>.
 *
 * Responsiveness strategy:
 * - `viewport` export sets initial-scale=1 and width=device-width, ensuring
 *   correct rendering on every screen from 320px to 4K.
 * - The CSS variable --header-h is set via a client script so the canvas
 *   fill calculation is always accurate.
 *
 * @module app/layout
 */

import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Outfit } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { GlobalErrorBoundary } from "@/components/error-boundary";
import { Toaster } from "@/components/ui/toaster";

/* ─── Font Configuration ─────────────────────────────────────────────────── */

/**
 * Inter — primary sans-serif body font.
 * Subset to latin only to reduce bundle size.
 */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

/**
 * Outfit — display font for headings, giving a futuristic rounded feel.
 */
const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

/**
 * JetBrains Mono — monospace font for code, node labels, and metrics.
 */
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

/* ─── Metadata ───────────────────────────────────────────────────────────── */

/** @see https://nextjs.org/docs/app/api-reference/functions/generate-metadata */
export const metadata: Metadata = {
  title: {
    default: "AetherWeave — Sentient Architecture Loom",
    template: "%s | AetherWeave",
  },
  description:
    "AetherWeave is an AI-powered 3D living architecture loom that evolves, " +
    "debates, and grows your software architecture in real-time.",
  keywords: [
    "architecture",
    "AI",
    "evolutionary algorithms",
    "3D",
    "LangGraph",
    "neural network",
  ],
  authors: [{ name: "AetherWeave Team" }],
  creator: "AetherWeave",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000"
  ),
  openGraph: {
    type: "website",
    locale: "en_US",
    title: "AetherWeave — Sentient Architecture Loom",
    description:
      "Evolve your software architecture with AI-driven 3D neural forests.",
    siteName: "AetherWeave",
  },
  twitter: {
    card: "summary_large_image",
    title: "AetherWeave",
    description: "Sentient 3D living architecture loom powered by AI.",
  },
  robots: { index: true, follow: true },
};

/**
 * Viewport configuration — ensures proper mobile rendering.
 * `themeColor` matches our primary void background for Android Chrome.
 */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,          // allow pinch-zoom for accessibility
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#080c16" },
  ],
  colorScheme: "dark",
};

/* ─── Root Layout Component ─────────────────────────────────────────────── */

/**
 * RootLayout — wraps every page in the application.
 *
 * @param props.children - The active page or nested layout rendered by Next.js.
 * @returns HTML document structure with fonts, providers, and error boundary.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${inter.variable} ${outfit.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Prevent FOUC on theme load */}
        <script
          dangerouslySetInnerHTML={{
            __html: `document.documentElement.classList.add('dark');`,
          }}
        />
      </head>
      <body className="min-h-dvh bg-void-950 text-foreground font-sans antialiased overflow-x-hidden">
        {/*
         * GlobalErrorBoundary catches any uncaught React errors and renders
         * a fallback UI instead of crashing the full page.
         */}
        <GlobalErrorBoundary>
          {/*
           * Providers wraps React Query, Zustand HydrationBoundary, and
           * any other context providers needed globally.
           */}
          <Providers>
            {children}

            {/* Radix Toast renderer — must be outside page content */}
            <Toaster />
          </Providers>
        </GlobalErrorBoundary>
      </body>
    </html>
  );
}
