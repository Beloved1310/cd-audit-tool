import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        rag: {
          red: "#b91c1c",
          amber: "#d97706",
          green: "#15803d",
        },
        /** Dark UI shell — emerald-tinted charcoal */
        app: {
          bg: "#060a08",
          surface: "#0c1411",
          raised: "#111b17",
          border: "#1a332a",
          muted: "#8fb3a3",
          accent: "#34d399",
          "accent-hover": "#6ee7b7",
          "accent-dim": "#065f46",
        },
      },
    },
  },
  plugins: [],
};

export default config;
