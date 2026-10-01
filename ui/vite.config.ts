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
        manualChunks: {
          "vendor-molstar": ["molstar/lib/apps/viewer/app"],
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
