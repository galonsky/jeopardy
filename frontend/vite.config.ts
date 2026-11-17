import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const backendUrl = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const websocketUrl = backendUrl.replace(/^http/, "ws");

export default defineConfig({
  base: "/static/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    proxy: {
      "/api": { target: backendUrl, changeOrigin: true },
      "/oidc": { target: backendUrl, changeOrigin: true },
      "/admin": { target: backendUrl, changeOrigin: true },
      "/ws": { target: websocketUrl, ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/index.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  test: { include: ["src/**/*.test.{ts,tsx}"] },
});
