import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Django API runs on :8000 during development. Proxying /api keeps the
// browser on one origin, so no CORS configuration is needed locally.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Any *.e2b.app host is the sandbox preview proxy. Listing them
    // explicitly keeps `npm run dev` working on a normal machine too.
    allowedHosts: [".e2b.app", "localhost"],
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  // The sandbox preview serves the built bundle. No HMR, no optimised-dep
  // chunks, so a browser can never end up with half-old / half-new modules
  // (which is what produces "Cannot read properties of null (reading 'useState')").
  preview: {
    port: 5173,
    host: true,
    allowedHosts: [".e2b.app", "localhost"],
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
