import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      // A aba Radar fala com /api/radar (funcao Vercel). Em dev, suba o
      // espelho local com `node scripts/radar-api-dev.mjs` — sem ele, so a
      // aba Radar fica sem dados; o resto do app nao passa por aqui.
      "/api": "http://localhost:8788",
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
