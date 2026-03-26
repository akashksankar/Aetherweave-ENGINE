import type { Config } from "tailwindcss";
import { fontFamily } from "tailwindcss/defaultTheme";

/**
 * Tailwind CSS configuration for AetherWeave.
 *
 * Design system foundations:
 * - Dark cyber-organic theme using CSS custom properties.
 * - Custom "aether" colour scale for the bioluminescent glow palette.
 * - Extended animation library for neural-growth and pulse effects.
 * - All glass / blur utilities are included via the experimental future flags.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./pages/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      /** ---------- Colour palette ---------- */
      colors: {
        /** Base dark layers */
        void: {
          950: "hsl(240 20% 3%)",
          900: "hsl(240 18% 6%)",
          800: "hsl(240 16% 9%)",
          700: "hsl(240 14% 13%)",
        },
        /** Bioluminescent cyan — primary accent */
        aether: {
          50:  "hsl(185 100% 97%)",
          100: "hsl(185 95% 90%)",
          200: "hsl(185 90% 75%)",
          300: "hsl(185 88% 60%)",
          400: "hsl(185 90% 45%)",
          500: "hsl(185 95% 35%)",
          600: "hsl(185 95% 27%)",
          700: "hsl(185 90% 20%)",
          800: "hsl(185 85% 14%)",
          900: "hsl(185 80% 9%)",
        },
        /** Neural violet — secondary accent */
        synapse: {
          50:  "hsl(270 100% 97%)",
          100: "hsl(270 95% 90%)",
          200: "hsl(270 90% 78%)",
          300: "hsl(270 88% 65%)",
          400: "hsl(270 85% 55%)",
          500: "hsl(270 80% 45%)",
          600: "hsl(270 80% 35%)",
          700: "hsl(270 75% 25%)",
          800: "hsl(270 70% 17%)",
          900: "hsl(270 65% 10%)",
        },
        /** Mutation amber — warning / highlight tones */
        mutagen: {
          50:  "hsl(40 100% 97%)",
          100: "hsl(40 95% 88%)",
          200: "hsl(40 95% 70%)",
          300: "hsl(38 95% 55%)",
          400: "hsl(35 95% 45%)",
          500: "hsl(32 95% 38%)",
        },

        /** shadcn/ui semantic tokens (mapped to our palette above) */
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },

      /** ---------- Typography ---------- */
      fontFamily: {
        sans: ["var(--font-inter)", ...fontFamily.sans],
        mono: ["var(--font-jetbrains)", ...fontFamily.mono],
        display: ["var(--font-outfit)", ...fontFamily.sans],
      },

      /** ---------- Border radius ---------- */
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },

      /** ---------- Animations ---------- */
      keyframes: {
        /** Bioluminescent node pulse — intensity oscillation */
        "aether-pulse": {
          "0%, 100%": { opacity: "1", filter: "brightness(1)" },
          "50%": { opacity: "0.7", filter: "brightness(1.4)" },
        },
        /** Slow float for 3D labels */
        "float-y": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
        /** Neural growth — element slides in from left */
        "slide-in-left": {
          from: { transform: "translateX(-100%)", opacity: "0" },
          to:   { transform: "translateX(0)",     opacity: "1" },
        },
        /** Shimmer for loading skeleton */
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        /** Accordion */
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
        /** Fade in */
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "aether-pulse": "aether-pulse 3s ease-in-out infinite",
        "float-y": "float-y 4s ease-in-out infinite",
        "slide-in-left": "slide-in-left 0.3s ease-out",
        shimmer: "shimmer 2s linear infinite",
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.4s ease-out",
      },

      /** ---------- Box shadow / glow ---------- */
      boxShadow: {
        "aether-glow": "0 0 20px hsl(185 90% 45% / 0.4), 0 0 60px hsl(185 90% 45% / 0.15)",
        "synapse-glow": "0 0 20px hsl(270 80% 55% / 0.4), 0 0 60px hsl(270 80% 55% / 0.15)",
        "mutagen-glow": "0 0 20px hsl(38 95% 55% / 0.4)",
        "glass": "inset 0 1px 0 rgb(255 255 255 / 0.08), 0 4px 24px rgb(0 0 0 / 0.4)",
      },

      /** ---------- Backdrop blur ---------- */
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
