import type { NextConfig } from "next";

/**
 * Next.js 15 configuration for AetherWeave frontend.
 *
 * Key decisions:
 * - `transpilePackages` ensures the shared workspace package is compiled correctly.
 * - Strict source maps for readable stack traces in development.
 * - CORS-safe rewrites proxy all /api calls to the FastAPI backend,
 *   so the browser never sees cross-origin requests (avoids CORS preflight).
 */
const nextConfig: NextConfig = {
  /** Transpile the monorepo shared package rather than treating it as raw ESM */
  transpilePackages: ["@aetherweave/shared"],

  /** Enable standalone output for minimal Docker images */
  output: "standalone",

  /** Enable React compiler (Babel-less RSC transforms in Next.js 15) */
  experimental: {
    reactCompiler: false, // Enable once React Compiler is stable
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },

  /** Image optimisation — allow backend host for any node icons */
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost" },
      { protocol: "https", hostname: "**.aetherweave.app" },
    ],
  },

  /** Proxy /api/* and /ws/* to the FastAPI backend during development */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },

  /** Strict source maps in all environments for easier debugging */
  productionBrowserSourceMaps: false,

  /** Power Source Header for the cyber-organic theme Easter egg */
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Powered-By", value: "AetherWeave Neural Engine" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },

  /** Webpack aliases so three.js tree-shaking works with R3F */
  webpack(config) {
    config.externals = config.externals || [];
    // three is a browser-only library — avoid SSR bundling issues
    config.resolve.alias = {
      ...config.resolve.alias,
    };
    return config;
  },
};

export default nextConfig;
