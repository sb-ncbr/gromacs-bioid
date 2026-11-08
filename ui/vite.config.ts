import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    include: ["molstar/lib/apps/viewer/app"],
  },
  build: {
    rollupOptions: {
      output: {
        // Only Mol* itself: the object form also pulled Mol*'s dependencies
        // (React among them) into this chunk, so the front page preloaded
        // all 4.7 MB of it.
        manualChunks(id) {
          if (id.includes("/node_modules/molstar/")) return "vendor-molstar";
          // React and tslib are shared by the page and Mol*; left unassigned, Rollup put
          // them in the Mol* chunk and the entry imported them from there.
          if (/\/node_modules\/(react|react-dom|scheduler|tslib)\//.test(id)) return "vendor-react";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/runs": "http://localhost:8000",
      "/files": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
