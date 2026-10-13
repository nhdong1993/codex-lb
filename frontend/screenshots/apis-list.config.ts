import { defineConfig } from "@playwright/test";

const port = process.env.SCREENSHOT_PORT ?? "4195";
export default defineConfig({
  testDir: ".",
  testMatch: "apis-list.spec.ts",
  timeout: 60_000,
  workers: 1,
  use: { viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 },
  webServer: {
    command: `bun run build && bun run preview --port ${port}`,
    port: Number(port),
    timeout: 120_000,
    reuseExistingServer: false,
  },
});
