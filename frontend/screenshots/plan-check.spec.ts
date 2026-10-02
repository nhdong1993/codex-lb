import { expect, test } from "@playwright/test";
import path from "node:path";

import { accounts, accountTrends, authSession, overview, settings, upstreamProxyAdmin } from "./fixtures";
import { createTelemetryConsent } from "../src/test/mocks/factories";

const directory = process.env.PLAN_CHECK_SCREENSHOTS;
for (const mode of ["list", "grid", "detail"]) {
  test(`plan verification replaces old countdown in ${mode}`, async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-10-02T08:00:00Z"));
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.addInitScript((view) => localStorage.setItem("codex-lb-accounts-view-mode", view), mode);
    let planCheckPending = false;
    const account = { ...accounts[0], planType: "plus", status: "active", displayName: "Personal Plus",
      email: "personal@example.com", alias: "Personal Plus",
      subscription: { activeUntil: "2026-10-04T05:54:59Z", lastCheckedAt: "2026-10-02T04:11:03Z", source: "subscriptions_api" },
    };
    await page.route("**/api/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === "/api/dashboard/overview") return route.fulfill({ json: overview });
      if (pathname === "/api/settings/telemetry") return route.fulfill({ json: createTelemetryConsent({ state: "disabled" }) });
      if (pathname === "/api/runtime/version") return route.fulfill({ json: {
        currentVersion: "1.25.0-beta.6", updateAvailable: false,
        checkedAt: "2026-10-02T08:00:00Z", releaseUrl: "https://github.com/Soju06/codex-lb/releases/latest",
      } });
      if (pathname.endsWith("/usage-reset-credits")) return route.fulfill({ json: {
        accountId: account.accountId, rateLimitResetCredits: { availableCount: 3 },
      } });
      return route.fulfill({ json:
        pathname === "/api/dashboard-auth/session" ? authSession
        : pathname === "/api/accounts" ? { accounts: [{ ...account, planCheckPending }] }
        : pathname === "/api/settings" ? settings
        : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
        : pathname.endsWith("/trends") ? accountTrends[account.accountId] ?? { primary: [], secondary: [] }
        : pathname.endsWith("/summary") ? { ...account, planCheckPending }
        : {} });
    });
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 });
      planCheckPending = false;
      await page.goto("http://127.0.0.1:4196/accounts?lang=en");
      await expect(page.getByText(/1d 21h/).first()).toBeVisible();
      if (directory) await page.screenshot({ path: path.join(directory, `before-${mode}-${width}.png`), animations: "disabled" });
      planCheckPending = true;
      await page.reload();
      await expect(page.getByText("Verifying plan").first()).toBeVisible();
      await expect(page.getByText(/1d 21h/)).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (directory) await page.screenshot({ path: path.join(directory, `after-${mode}-${width}.png`), animations: "disabled" });
    }
  });
}
