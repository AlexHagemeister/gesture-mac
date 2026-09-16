import { defineConfig } from "vite";

// Builds into the Python package so `uv run gesture-mac` serves the page
// with no node at runtime. The dev server proxies the API and the socket
// to a running app (default port 8765; see config.json's hud_port).
export default defineConfig({
  base: "./",
  build: { outDir: "../../gesture_mac/ui/static", emptyOutDir: true },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
});
