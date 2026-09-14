import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend base URL for dev-proxy target (the API itself, not the browser).
const BACKEND_URL = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

// Contract paths (14_API_CONTRACT_V1.md) are served WITHOUT an /api prefix,
// so the dev server proxies each known top-level path to FastAPI. The browser
// always uses relative URLs -> no CORS issues, preview-safe.
const API_PATHS = [
  "/health",
  "/auth",
  "/books",
  "/nodes",
  "/test-sessions",
  "/questions",
  "/progress",
  "/analytics",
  "/goals",
  "/planner",
  "/tasks",
  "/schedules",
  "/school-day-overrides",
  "/class-sessions",
  "/taught-lessons",
  "/homework",
  "/exams",
  "/rewards",
  "/telegram",
  "/users",
];

const proxy = Object.fromEntries(
  API_PATHS.map((p) => [p, { target: BACKEND_URL, changeOrigin: true }]),
);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Dev-only: allow proxied preview hosts (e.g. *.e2b.app).
    allowedHosts: true,
    proxy,
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    allowedHosts: true,
    proxy,
  },
});
