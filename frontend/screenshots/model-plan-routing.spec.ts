import path from "node:path";
import { mkdir } from "node:fs/promises";
import { expect, test } from "@playwright/test";

import { accounts, authSession, overview, settings, upstreamProxyAdmin } from "./fixtures";
import { createTelemetryConsent } from "../src/test/mocks/factories";

const before = process.env.SCREENSHOT_PHASE === "before";
const outputDir = process.env.SCREENSHOT_DIR ?? "/tmp/codex-model-plan-routing/screenshots";
const examplePolicies = {
  "gpt-5.6-terra": ["free"],
  "gpt-5.6-luna": ["free"],
  "gpt-6-luna": ["free"],
};
const titles = {
  en: { routing: "Routing", plans: "Subscription model plans" },
  ko: { routing: "Routing", plans: "구독 모델 플랜" },
  "zh-CN": { routing: "路由", plans: "订阅模型套餐" },
};

for (const locale of before ? (["en"] as const) : (["en", "ko", "zh-CN"] as const)) {
  test(`routing model plans ${before ? "before" : "after"} ${locale}`, async ({ page }) => {
    await mkdir(outputDir, { recursive: true });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.addInitScript(() => localStorage.setItem("codex-lb-theme", "light"));
    let policies: Record<string, string[]> = examplePolicies;
    await page.route("**/api/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      // Every API request is fulfilled/aborted here, never forwarded to a backend.
      const fixtures: Record<string, unknown> = {
        "/api/dashboard-auth/session": authSession,
        "/api/accounts": { accounts },
        "/api/settings": { ...settings, modelPlanRoutingPolicies: policies },
        "/api/settings/upstream-proxy": upstreamProxyAdmin,
        "/api/settings/telemetry": createTelemetryConsent({ state: "disabled" }),
        "/api/dashboard/overview": overview,
        "/api/model-sources/": { sources: [] },
        "/api/models": {
          models: [
            ...Object.keys(examplePolicies).map((id) => ({ id, name: id })),
            { id: "image-only", name: "Image-only", imageOnly: true },
            { id: "source-only", name: "Source-only", sourceOnly: true },
          ],
        },
        "/api/runtime/version": {
          currentVersion: "1.25.0-beta.6",
          updateAvailable: false,
          checkedAt: "2026-10-11T00:00:00Z",
          releaseUrl: "https://github.com/Soju06/codex-lb/releases/latest",
        },
      };
      return pathname in fixtures ? route.fulfill({ json: fixtures[pathname] }) : route.abort();
    });
    await page.route(
      (url) => url.pathname === "/health" || url.pathname === "/health/ready",
      (route) => route.fulfill({ json: { status: "ok" } }),
    );
    await page.goto(`/settings?advanced=1&lang=${locale}`, { waitUntil: "domcontentloaded" });
    await page.addStyleTag({
      content: "*, *::before, *::after { animation: none !important; transition: none !important; }",
    });
    const heading = page.getByRole("heading", { name: titles[locale].routing, exact: true });
    await expect(heading).toBeVisible();
    await heading.evaluate((node) => node.closest("section")!.scrollIntoView({ block: "start" }));
    await page.screenshot({
      path: path.join(outputDir, `routing-settings-${before ? "before" : "after"}-${locale}-desktop.png`),
    });
    if (before) {
      await expect(page.getByRole("region", { name: titles[locale].plans })).toHaveCount(0);
      return;
    }

    const editor = page.getByRole("region", { name: titles[locale].plans });
    await expect(editor).toBeVisible();
    for (const model of Object.keys(examplePolicies))
      await expect(editor.getByText(model, { exact: true })).toBeVisible();
    await editor.screenshot({ path: path.join(outputDir, `model-plan-routing-after-${locale}-desktop.png`) });
    await page.setViewportSize({ width: 390, height: 1000 });
    await editor.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await editor.screenshot({ path: path.join(outputDir, `model-plan-routing-after-${locale}-mobile.png`) });

    if (locale === "en") {
      policies = {};
      await page.setViewportSize({ width: 1440, height: 1250 });
      await page.reload();
      await expect(page.getByText("No restrictions configured.")).toBeVisible();
      await editor.screenshot({ path: path.join(outputDir, "model-plan-routing-after-en-empty.png") });
      await editor.getByRole("combobox", { name: "Subscription model" }).click();
      await expect(page.getByRole("option")).toHaveCount(3);
      await expect(page.getByRole("option", { name: "image-only" })).toHaveCount(0);
      await expect(page.getByRole("option", { name: "source-only" })).toHaveCount(0);
    }
  });
}
