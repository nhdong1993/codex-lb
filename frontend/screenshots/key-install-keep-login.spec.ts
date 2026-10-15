import path from "node:path";
import { mkdir } from "node:fs/promises";
import { expect, test } from "@playwright/test";

const before = process.env.SCREENSHOT_PHASE === "before";
const outputDir = process.env.SCREENSHOT_DIR ?? "/tmp/codex-key-install-keep-login/screenshots";
const apiKey = "sk-clb-screenshot-key";
const profile = {
  name: "Production client",
  keyPrefix: "sk-clb-screensh…",
  isActive: true,
  createdAt: "2026-08-01T08:00:00Z",
  expiresAt: "2027-08-01T08:00:00Z",
  lastUsedAt: "2026-10-14T03:59:00Z",
  allowedModels: ["gpt-5.6-luna", "gpt-6.1-sol"],
  enforcedModel: null,
  allowedReasoningEfforts: null,
  enforcedReasoningEffort: null,
  enforcedServiceTier: null,
  trafficClass: "foreground",
  transportPolicyOverride: null,
};
const usage = {
  request_count: 9,
  total_tokens: 12_500,
  cached_input_tokens: 2_500,
  total_cost_usd: 0.42,
  limits: [],
  upstream_limits: [],
  account_pool_usage: null,
};

for (const [theme, viewport] of [
  ["light", { width: 1440, height: 1400 }],
  ["dark", { width: 1440, height: 1400 }],
  ["light", { width: 390, height: 1400 }],
] as const) {
  test(`key install keep-login ${before ? "before" : "after"} ${theme} ${viewport.width}`, async ({ page }) => {
    await mkdir(outputDir, { recursive: true });
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.addInitScript((value) => localStorage.setItem("codex-lb-theme", value), theme);
    await page.route("**/api/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      // Every API request is fulfilled/aborted here, never forwarded to a backend.
      if (pathname === "/api/key-dashboard/install-script") {
        return route.fulfill({ body: `#!/usr/bin/env bash\n# ${apiKey}\n`, contentType: "text/plain" });
      }
      const fixtures: Record<string, unknown> = {
        "/api/key-dashboard/profile": profile,
        "/api/key-dashboard/request-logs": { requests: [], total: 0, hasMore: false },
        "/api/key-dashboard/group": { groupName: null, from: "2026-09-14T00:00:00Z", until: "2026-10-14T00:00:00Z", members: [] },
      };
      return pathname in fixtures ? route.fulfill({ json: fixtures[pathname] }) : route.abort();
    });
    await page.route("**/v1/usage", (route) => route.fulfill({ json: usage }));
    await page.route(
      (url) => url.pathname === "/health" || url.pathname === "/health/ready",
      (route) => route.fulfill({ json: { status: "ok" } }),
    );
    await page.goto("/key-dashboard?lang=en", { waitUntil: "domcontentloaded" });
    await page.addStyleTag({
      content: "*, *::before, *::after { animation: none !important; transition: none !important; }",
    });
    await page.getByLabel("API key").fill(apiKey);
    await page.getByRole("button", { name: "Open dashboard" }).click();
    await page.getByRole("tab", { name: "Install" }).click();
    await expect(page.getByRole("button", { name: "Copy command" })).toBeVisible();
    const suffix = `${before ? "before" : "after"}-${theme}-${viewport.width}`;
    await page.screenshot({ path: path.join(outputDir, `install-${suffix}.png`), fullPage: true });
    if (before) return;
    await page.getByRole("button", { name: "Copy script" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.screenshot({ path: path.join(outputDir, `confirm-${suffix}.png`) });
  });
}
