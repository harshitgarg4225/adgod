import type { Config } from "tailwindcss";

/**
 * Salmor design tokens.
 *
 * One source of truth for colour, type, spacing, radius, elevation and motion.
 * Green = growth/money (primary, trust); saffron = warmth/delight (accent, used
 * sparingly for celebratory and human moments — the "Saathi" personality).
 * Backwards-compatible aliases (brand.DEFAULT/dark/light, hot/warm/cold) are kept so
 * existing screens keep rendering while they migrate onto the richer scale.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0B7A4B",
          dark: "#075c39",
          light: "#E6F4EE",
          50: "#ECFAF3",
          100: "#D2F2E2",
          200: "#A6E6C7",
          300: "#6FD3A5",
          400: "#36B981",
          500: "#0B7A4B",
          600: "#096B42",
          700: "#075c39",
          800: "#064A2E",
          900: "#053C26",
        },
        // Saffron accent — warmth, celebration, the human "Saathi" touch.
        accent: {
          DEFAULT: "#F2820D",
          light: "#FEF1E2",
          50: "#FEF6EC",
          100: "#FDE9CF",
          200: "#FBCF95",
          300: "#F8B25B",
          400: "#F2820D",
          500: "#D96D05",
          600: "#B25705",
        },
        // Lead temperature.
        hot: { DEFAULT: "#E11D48", light: "#FFE4EA" },
        warm: { DEFAULT: "#F59E0B", light: "#FEF3DC" },
        cold: { DEFAULT: "#64748B", light: "#EEF2F6" },
        // Ink + surface neutrals (slightly warm grey, friendlier than pure slate).
        ink: {
          DEFAULT: "#0F172A",
          soft: "#334155",
          muted: "#64748B",
          faint: "#94A3B8",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        deva: ["var(--font-deva)", "var(--font-sans)", "sans-serif"],
      },
      fontSize: {
        // A compact, mobile-first type ramp (rem so OS font-scaling is respected).
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.875rem", { lineHeight: "1.35rem" }],
        base: ["1rem", { lineHeight: "1.55rem" }],
        lg: ["1.125rem", { lineHeight: "1.6rem" }],
        xl: ["1.3125rem", { lineHeight: "1.7rem" }],
        "2xl": ["1.5rem", { lineHeight: "1.9rem", letterSpacing: "-0.01em" }],
        "3xl": ["1.875rem", { lineHeight: "2.2rem", letterSpacing: "-0.02em" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem", letterSpacing: "-0.02em" }],
      },
      borderRadius: {
        lg: "0.75rem",
        xl: "1rem",
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      boxShadow: {
        // A 3-step elevation language — soft, low-spread, premium.
        xs: "0 1px 2px 0 rgb(15 23 42 / 0.05)",
        card: "0 1px 3px 0 rgb(15 23 42 / 0.06), 0 1px 2px -1px rgb(15 23 42 / 0.05)",
        elevated: "0 4px 16px -2px rgb(15 23 42 / 0.10), 0 2px 6px -2px rgb(15 23 42 / 0.06)",
        float: "0 12px 32px -8px rgb(15 23 42 / 0.18)",
        brand: "0 6px 20px -6px rgb(11 122 75 / 0.45)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pop": {
          "0%": { transform: "scale(0.8)", opacity: "0" },
          "60%": { transform: "scale(1.06)", opacity: "1" },
          "100%": { transform: "scale(1)" },
        },
        "sheet-up": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out both",
        "slide-up": "slide-up 0.35s cubic-bezier(0.22,1,0.36,1) both",
        "scale-in": "scale-in 0.2s ease-out both",
        pop: "pop 0.4s cubic-bezier(0.22,1,0.36,1) both",
        "sheet-up": "sheet-up 0.3s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
