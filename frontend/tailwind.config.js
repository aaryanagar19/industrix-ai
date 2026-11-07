/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)", surface: "rgb(var(--surface) / <alpha-value>)", surface2: "rgb(var(--surface2) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)", ink: "rgb(var(--ink) / <alpha-value>)", muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)", ok: "rgb(var(--ok) / <alpha-value>)", warn: "rgb(var(--warn) / <alpha-value>)",
        orange: "rgb(var(--orange) / <alpha-value>)", danger: "rgb(var(--danger) / <alpha-value>)",
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
      keyframes: { pulseRing: { "0%": { transform: "scale(1)", opacity: ".7" }, "100%": { transform: "scale(2.2)", opacity: "0" } } },
      animation: { pulseRing: "pulseRing 1.8s ease-out infinite" },
    },
  },
  plugins: [],
};
