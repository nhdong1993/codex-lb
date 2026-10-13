import { expect, test } from "@playwright/test";
import path from "node:path";
import { apiKeys, authSession, models, settings } from "./fixtures";

const directory = process.env.APIS_LIST_SCREENSHOTS;
const fleet = [
  { ...apiKeys[0], name: "Production", expiresAt: "2026-12-01T12:00:00Z", pooledCapacityCreditsPrimary: 500, pooledRemainingPercentPrimary: 85, pooledRemainingPercentSecondary: 72, lastUsedAt: "2026-09-30T12:00:00Z", usageSummary: { requestCount: 2400, totalTokens: 1_500_000, cachedInputTokens: 100_000, totalCostUsd: 8.5 } },
  { ...apiKeys[1], name: "Unused development", expiresAt: null, lastUsedAt: null, usageSummary: null },
  { ...apiKeys[2], name: "Archived client", lastUsedAt: "2026-09-20T12:00:00Z", usageSummary: null },
  { ...apiKeys[1], id: "key_spare", name: "Unused backup", keyPrefix: "sk-backup", lastUsedAt: null, isActive: false, usageSummary: { requestCount: 0, totalTokens: 0, cachedInputTokens: 0, totalCostUsd: 0 } },
];

for (const language of ["en", "ko", "zh-CN"]) {
  test(`APIs List fits small screens and supports unused filtering (${language})`, async ({ page }) => {
    // Vite's /api proxy also matches /apis; serve the built shell for this SPA route.
    await page.route("**/apis?*", async (route) => {
      const response = await page.request.get(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4195"}/index.html`);
      return route.fulfill({ response });
    });
    await page.clock.setFixedTime(new Date("2026-10-01T12:00:00Z"));
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/**", (route) => {
      const p = new URL(route.request().url()).pathname;
      const keyId = p.split("/")[3];
      return route.fulfill({ json: p === "/api/dashboard-auth/session" ? authSession
        : p === "/api/api-keys" || p === "/api/api-keys/" ? fleet
        : p.endsWith("/trends") ? { keyId, cost: [{ t: "2026-10-01T12:00:00Z", v: 1 }], tokens: [{ t: "2026-10-01T12:00:00Z", v: 10 }] }
        : p.endsWith("/usage-7d") ? { keyId, totalTokens: 10, totalCostUsd: 1, totalRequests: 2, cachedInputTokens: 0, accountCosts: [] }
        : p === "/api/settings" ? settings : p === "/api/models" ? models : {} });
    });
    await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4195"}/apis?lang=${language}`);
    await expect(page.getByTestId("api-key-info")).toBeVisible();
    if (directory && language === "en") await page.screenshot({ path: path.join(directory, "detail-desktop.png"), fullPage: true, animations: "disabled" });
    const views = page.getByRole("group").filter({ has: page.getByRole("button", { name: language === "en" ? "List view" : language === "ko" ? "목록 보기" : "列表视图", exact: true }) });
    await views.getByRole("button").nth(1).click();
    const rows = page.getByTestId("api-list-overview-row");
    await expect(rows).toHaveCount(4);
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const heights = await rows.evaluateAll((items) => items.map((node) => node.getBoundingClientRect().height));
      expect(Math.max(...heights)).toBeLessThanOrEqual(width >= 1024 ? 110 : 260);
      await rows.first().evaluate((node) => node.scrollIntoView({ block: "center" }));
      if (directory && [1440, 320].includes(width)) await page.screenshot({ path: path.join(directory, `list-${language}-${width}.png`), animations: "disabled" });
    }
    if (language !== "en") return;
    await page.getByRole("combobox", { name: "Filter keys by usage" }).click();
    await page.getByRole("option", { name: "Key not used", exact: true }).click();
    await expect(rows).toHaveCount(2);
    await rows.first().focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog", { name: "Details for Unused development" })).toBeVisible();
    await page.getByRole("button", { name: "Actions", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
    const editDialog = page.getByRole("dialog", { name: "Edit API key", exact: true });
    await expect(editDialog).toBeVisible();
    const editBounds = (await editDialog.boundingBox())!;
    expect(editBounds.y).toBeGreaterThanOrEqual(0);
    expect(editBounds.y + editBounds.height).toBeLessThanOrEqual(1000);
    await editDialog.getByRole("button", { name: "Close", exact: true }).click();
    await expect(editDialog).toHaveCount(0);
    await expect(page.locator('[data-slot="dropdown-menu-content"]')).toHaveCount(0);
    await expect(page.getByRole("dialog", { name: "Details for Unused development" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator('[data-slot="dialog-content"]')).toHaveCount(0);
    await expect(rows).toHaveCount(2);
    await page.getByRole("button", { name: "Detail view", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Filter keys by usage" })).toHaveText(/Key not used/);
    await page.getByRole("button", { name: "List view", exact: true }).click();
    await page.reload();
    await expect(rows).toHaveCount(4);
    // The selected-key URL reopens its details on reload.
    await page.keyboard.press("Escape");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole("button", { name: "Lifetime requests: Not sorted" }).click();
    await expect(rows.first()).toContainText("Unused backup");
    await page.getByRole("button", { name: "Lifetime requests: Ascending" }).click();
    await expect(rows.first()).toContainText("Production");
  });
}
