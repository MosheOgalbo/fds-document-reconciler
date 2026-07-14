/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#16233B",
          soft: "#4B5A73",
          faint: "#7C8AA0",
        },
        paper: {
          DEFAULT: "#F6F5F0",
          raised: "#FFFFFF",
        },
        rule: "#E0DCCF",
        brass: {
          DEFAULT: "#A9822F",
          soft: "#F1E8D2",
          dark: "#8A6A24",
        },
        match: {
          DEFAULT: "#3F6B4A",
          soft: "#E7EFE7",
        },
        diff: {
          DEFAULT: "#B8862E",
          soft: "#F5EBD6",
        },
        missing: {
          DEFAULT: "#A14A3D",
          soft: "#F5E4E0",
        },
      },
      fontFamily: {
        display: ["'Source Serif 4'", "Georgia", "serif"],
        sans: ["'IBM Plex Sans'", "'IBM Plex Sans Hebrew'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "5px",
        md: "6px",
        lg: "8px",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(22, 35, 59, 0.06), 0 1px 6px -1px rgba(22, 35, 59, 0.05)",
      },
    },
  },
  plugins: [],
};
