/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": API, "/ws": { target: API, ws: true } } },
  build: { chunkSizeWarningLimit: 1200 },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test/setup.ts", css: false },
});
