import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

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

const phase = before ? "before" : "after";
// One unbroken line stresses the expanded preview at narrow widths.
const longScriptLine = `curl --header 'Authorization: Bearer ${apiKey}' ${"https://codex-lb.example/api/key-dashboard/install-script?platform=windows".repeat(4)}`;

async function openInstall(page: Page, theme: "light" | "dark", viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript((value) => localStorage.setItem("codex-lb-theme", value), theme);
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    // Every API request is fulfilled/aborted here, never forwarded to a backend.
    if (pathname === "/api/key-dashboard/install-script") {
      return route.fulfill({ body: `#!/usr/bin/env bash\n# ${apiKey}\n${longScriptLine}\n`, contentType: "text/plain" });
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
}

for (const theme of ["light", "dark"] as const) {
  test(`key install windows preview ${phase} ${theme} 390`, async ({ page }) => {
    await mkdir(outputDir, { recursive: true });
    await openInstall(page, theme, { width: 390, height: 1400 });
    await page.locator("label").filter({ has: page.getByRole("radio", { name: "Windows" }) }).click();
    await expect(page.getByRole("radio", { name: "Windows" })).toBeChecked();
    await expect(page.getByText("codex-lb-windows.ps1").first()).toBeVisible();
    await page.getByText("Preview script").click();
    await expect(page.getByLabel("Preview script")).toBeVisible();
    const { scrollWidth, innerWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(innerWidth);
    await expect(page.getByText("Before you run")).toBeVisible();
    await expect(page.getByText("Keep your key private")).toBeVisible();
    await page.screenshot({ path: path.join(outputDir, `install-${phase}-windows-preview-${theme}-390.png`), fullPage: true });
  });
}

for (const [theme, viewport] of [
  ["light", { width: 1440, height: 1400 }],
  ["dark", { width: 1440, height: 1400 }],
  ["light", { width: 390, height: 1400 }],
] as const) {
  test(`key install keep-login ${before ? "before" : "after"} ${theme} ${viewport.width}`, async ({ page }) => {
    await mkdir(outputDir, { recursive: true });
    await openInstall(page, theme, viewport);
    const suffix = `${before ? "before" : "after"}-${theme}-${viewport.width}`;
    await page.screenshot({ path: path.join(outputDir, `install-${suffix}.png`), fullPage: true });
    const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    await writeFile(path.join(outputDir, `install-${suffix}.json`), `${JSON.stringify({ scrollHeight })}\n`);
    if (before) return;
    await page.getByRole("button", { name: "Copy script" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.screenshot({ path: path.join(outputDir, `confirm-${suffix}.png`) });
  });
}
