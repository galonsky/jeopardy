import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const frontend = process.cwd();
const repo = resolve(frontend, "..");
const e2eDatabase = "sqlite:////tmp/jeopardy-playwright.sqlite3";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://127.0.0.1:5174",
    browserName: "chromium",
    viewport: { width: 390, height: 844 },
  },
  webServer: [
    {
      command:
        "uv run --no-sync uvicorn config.asgi:application --app-dir backend --host 127.0.0.1 --port 8001",
      cwd: repo,
      env: { DATABASE_URL: e2eDatabase },
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
    },
    {
      command: "./node_modules/.bin/vite --host 127.0.0.1 --port 5174 --strictPort",
      cwd: frontend,
      env: { VITE_BACKEND_URL: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:5174/static/",
      reuseExistingServer: false,
    },
  ],
});
