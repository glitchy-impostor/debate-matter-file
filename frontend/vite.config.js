import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite base path is set at build time via VITE_BASE so the same code works
// for `npm run dev` (root) and GitHub Pages (/<repo>/). The deploy workflow
// passes VITE_BASE=/<repo>/ before `npm run build`.
export default defineConfig(() => ({
  plugins: [react()],
  base: process.env.VITE_BASE || "/",
  server: { port: 5173 },
}));
