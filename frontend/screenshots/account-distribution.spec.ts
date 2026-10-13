import { expect, test } from "@playwright/test";
import path from "node:path";
import { createTelemetryConsent } from "../src/test/mocks/factories";
import { accounts, accountTrends, authSession, overview, settings, upstreamProxyAdmin } from "./fixtures";

const directory = process.env.ACCOUNT_DISTRIBUTION_SCREENSHOTS;
const before = process.env.ACCOUNT_DISTRIBUTION_PHASE === "before";
const statuses = ["active", "active", "paused", "rate_limited", "quota_exceeded", "reauth_required", "deactivated"];
const plans = ["plus", "plus", "pro", "pro", "team", "free", "plus"];
const titles: Record<string, [string, string]> = {
  en: ["Accounts by plan", "Accounts by status"],
  ko: ["플랜별 계정", "상태별 계정"],
  "zh-CN": ["按套餐统计账户", "按状态统计账户"],
};
const sampleAccounts = accounts.map((account, index) => ({
  ...account,
  displayName: `Account ${index + 1}`,
  alias: `Account ${index + 1}`,
  email: `account-${index + 1}@example.com`,
  planType: plans[index],
  status: statuses[index],
}));

for (const mode of ["detail", "list", "grid"]) {
  for (const locale of before ? ["en"] : ["en", "ko", "zh-CN"]) {
    for (const theme of before ? ["light"] : ["light", "dark"]) {
      test(`account distributions in ${mode}, ${locale}, ${theme}`, async ({ page }) => {
        await page.clock.setFixedTime(new Date("2026-10-02T08:00:00Z"));
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.addInitScript(({ viewMode, selectedTheme }) => {
          localStorage.setItem("codex-lb-accounts-view-mode", viewMode);
          localStorage.setItem("codex-lb-theme", selectedTheme);
        }, { viewMode: mode, selectedTheme: theme });
        await page.route("**/api/**", (route) => {
          const pathname = new URL(route.request().url()).pathname;
          const accountId = pathname.split("/")[3];
          const account = sampleAccounts.find((item) => item.accountId === accountId) ?? sampleAccounts[0];
          return route.fulfill({ json:
            pathname === "/api/dashboard-auth/session" ? authSession
              : pathname === "/api/accounts" ? { accounts: sampleAccounts }
              : pathname === "/api/settings" ? settings
              : pathname === "/api/settings/telemetry" ? createTelemetryConsent({ state: "disabled" })
              : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
              : pathname === "/api/dashboard/overview" ? overview
              : pathname === "/api/runtime/version" ? {
                currentVersion: "1.25.0-beta.6", updateAvailable: false,
                checkedAt: "2026-10-02T08:00:00Z", releaseUrl: "https://github.com/Soju06/codex-lb/releases/latest",
              }
              : pathname.endsWith("/trends") ? accountTrends[account.accountId]
              : pathname.endsWith("/summary") ? account
              : pathname.endsWith("/usage-reset-credits") ? { accountId, rateLimitResetCredits: { availableCount: 0 } }
              : {} });
        });

        for (const width of before ? [1440, 390] : [1440, 768, 390, 320]) {
          await page.setViewportSize({ width, height: 1100 });
          await page.goto(`http://127.0.0.1:4207/accounts?lang=${locale}`);
          await expect(page.getByTestId("accounts-layout")).toBeVisible({ timeout: 15_000 });
          if (!before) {
            const charts = page.getByTestId("accounts-distribution-charts");
            await expect(charts).toBeVisible();
            await expect(charts.locator(".recharts-pie-sector path")).toHaveCount(10, { timeout: 15_000 });
            await expect(charts.getByRole("region")).toHaveCount(2);
            await expect(charts.getByTestId("donut-legend-list").first().getByRole("button")).toHaveCount(4);
            await expect(charts.getByTestId("donut-legend-list").last().getByRole("button")).toHaveCount(6);
            expect(await charts.getByTestId("donut-legend-list").last().evaluate((legend) => {
              const bounds = legend.getBoundingClientRect();
              return [...legend.querySelectorAll("button")].every((button) => {
                const row = button.getBoundingClientRect();
                return row.top >= bounds.top && row.bottom <= bounds.bottom + 1;
              });
            })).toBe(true);
            await expect(charts.getByTestId("donut-center-total")).toHaveText(["7", "7"]);
            for (const title of titles[locale]) {
              await expect(charts.getByRole("region", { name: title, exact: true })).toBeVisible();
            }
            if (locale === "en") {
              const plan = charts.getByRole("region", { name: "Accounts by plan", exact: true });
              await expect(plan.getByRole("button", { name: "Plus 3 (42.9%)", exact: true })).toBeVisible();
              const status = charts.getByRole("region", { name: "Accounts by status", exact: true });
              for (const label of ["Active", "Paused", "Rate limited", "Quota exceeded", "Re-auth required", "Deactivated"]) {
                const legend = status.getByRole("button", { name: new RegExp(label) });
                await expect(legend).toHaveCount(1);
                await expect(legend).toContainText("%");
              }
            }
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
          }
          const capture = locale === "en" && theme === "light" && width === 1440
            || mode === "list" && width === 390 && (locale === "en" || theme === "light");
          if (directory && capture) {
            if (!before && width === 390) await page.setViewportSize({ width, height: 1280 });
            await page.screenshot({ path: path.join(directory, `${before ? "before" : "after"}-${mode}-${locale}-${theme}-${width}.png`), animations: "disabled" });
          }
          if (!before && locale === "en" && theme === "light" && width === 1440) {
            const charts = page.getByTestId("accounts-distribution-charts");
            const deactivated = charts.getByRole("button", { name: "Deactivated 1 (14.3%)", exact: true });
            await deactivated.focus();
            await expect(deactivated).toBeFocused();
            await expect(deactivated).toHaveAttribute("data-active", "true");
            await expect(deactivated).toBeInViewport();
            await page.getByPlaceholder("Search accounts...").fill("no-such-account");
            await expect(page.getByText("No matching accounts", { exact: true })).toBeVisible();
            await expect(charts.getByTestId("donut-center-total")).toHaveText(["7", "7"]);
            await expect(charts.getByRole("button")).toHaveCount(10);
          }
        }
      });
    }
  }
}
