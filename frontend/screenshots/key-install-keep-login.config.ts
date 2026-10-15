import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const frontendDir =
  process.env.SCREENSHOT_FRONTEND_DIR ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const port = Number(process.env.SCREENSHOT_PORT ?? "4251");

export default defineConfig({
  testDir: ".",
  testMatch: "key-install-keep-login.spec.ts",
  outputDir: process.env.SCREENSHOT_RESULTS_DIR ?? "/tmp/codex-key-install-keep-login/screenshots/test-results",
  timeout: 180_000,
  workers: 1,
  expect: { timeout: 30_000 },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    viewport: { width: 1440, height: 1400 },
    deviceScaleFactor: 1,
    serviceWorkers: "block",
  },
  webServer: {
    cwd: frontendDir,
    command: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --strictPort --port ${port}`,
    env: { API_PROXY_TARGET: "http://127.0.0.1:9" },
    port,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
