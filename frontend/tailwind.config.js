/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        ink: {
          950: "#08090b",
          900: "#0c0e12",
          800: "#13161c",
          700: "#1a1e26",
          600: "#262b35",
          500: "#3a4150",
        },
        wire: {
          ir: "#7faedc",        // slate blue
          econ: "#34c39c",      // emerald
          business: "#e0a458",  // amber
        },
      },
      boxShadow: {
        wire: "0 1px 0 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.06)",
      },
    },
  },
  plugins: [],
};
