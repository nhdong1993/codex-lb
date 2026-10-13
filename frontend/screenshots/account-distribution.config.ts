import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "account-distribution.spec.ts",
  timeout: 60_000,
  workers: 2,
  use: { viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 },
  webServer: {
    cwd: "..",
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4207",
    port: 4207,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
