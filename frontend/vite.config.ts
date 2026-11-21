import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In Docker the API runs in the "backend" service; outside Docker it runs on localhost:8000.
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    // Windows bind mounts do not propagate file-change events into containers: poll instead.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true" },
    // The SPA calls relative URLs (/api/...), so browser and API share one origin (no CORS).
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
