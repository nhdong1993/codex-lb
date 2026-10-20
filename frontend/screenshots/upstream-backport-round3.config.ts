import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "upstream-backport-round3.spec.ts",
  timeout: 60_000,
  workers: 1,
  use: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
  webServer: {
    cwd: "..",
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4211",
    port: 4211,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
