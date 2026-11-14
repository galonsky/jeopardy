import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { resolve } from "node:path";

export default function globalSetup() {
  const databasePath = "/tmp/jeopardy-playwright.sqlite3";
  rmSync(databasePath, { force: true });
  execFileSync("make", ["sample"], {
    cwd: resolve(process.cwd(), ".."),
    env: { ...process.env, DATABASE_URL: "sqlite:////tmp/jeopardy-playwright.sqlite3" },
    stdio: "inherit",
  });
}
