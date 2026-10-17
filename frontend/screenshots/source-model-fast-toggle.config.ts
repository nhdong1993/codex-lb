import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: ".", testMatch: "source-model-fast-toggle.spec.ts", timeout: 30_000, workers: 1,
  use: { viewport: { width: 1440, height: 1400 }, deviceScaleFactor: 1 },
});
