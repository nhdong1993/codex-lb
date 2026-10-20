import { expect, test, type Locator, type Page } from "@playwright/test";
import path from "node:path";
import { createAccountSummary, createAccountTrends, createTelemetryConsent } from "../src/test/mocks/factories";
import type { AccountSummary, AccountTrendsResponse } from "../src/test/mocks/factories";
import { authSession, createRequestLogsResponse, filterOptions, overview, settings, upstreamProxyAdmin } from "./fixtures";

// Before/after evidence for the round-3 upstream backport UI changes. Synthetic
// fixtures only: no credentials, no live upstream.
const directory = process.env.BACKPORT_R3_SCREENSHOTS;
const before = process.env.BACKPORT_R3_PHASE === "before";
const BASE_URL = "http://127.0.0.1:4211";

async function mockApi(page: Page, accounts: AccountSummary[], trends: Record<string, AccountTrendsResponse> = {}) {
  await page.clock.setFixedTime(new Date("2026-10-20T08:00:00Z"));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const accountId = decodeURIComponent(pathname.split("/")[3] ?? "");
    const account = accounts.find((item) => item.accountId === accountId) ?? accounts[0];
    return route.fulfill({ json:
      pathname === "/api/dashboard-auth/session" ? authSession
        : pathname === "/api/accounts" ? { accounts }
        : pathname === "/api/settings" ? settings
        : pathname === "/api/settings/telemetry" ? createTelemetryConsent({ state: "disabled" })
        : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
        : pathname === "/api/dashboard/overview" ? { ...overview, accounts }
        : pathname === "/api/request-logs" ? createRequestLogsResponse([], 0, false)
        : pathname === "/api/request-logs/options" ? filterOptions
        : pathname === "/api/runtime/version" ? {
          currentVersion: "1.25.0-beta.6", updateAvailable: false,
          checkedAt: "2026-10-20T08:00:00Z", releaseUrl: "https://github.com/Soju06/codex-lb/releases/latest",
        }
        : pathname.endsWith("/trends") ? (trends[account.accountId] ?? createAccountTrends(account.accountId))
        : pathname.endsWith("/summary") ? account
        : pathname.endsWith("/usage-reset-credits") ? { accountId, rateLimitResetCredits: { availableCount: 0 } }
        : {} });
  });
}

async function shoot(target: Page | Locator, name: string) {
  if (directory) {
    await target.screenshot({ path: path.join(directory, `${before ? "before" : "after"}-${name}.png`), animations: "disabled" });
  }
}

const recoveryAccounts = [
  createAccountSummary({
    accountId: "acc_recover", email: "recover@example.com", displayName: "Recovery account",
    status: "deactivated", availableResetCredits: 1,
  }),
  createAccountSummary({ accountId: "acc_reauth", email: "reauth@example.com", displayName: "Reauth account", status: "reauth_required" }),
  createAccountSummary({ accountId: "acc_paused", email: "paused@example.com", displayName: "Paused account", status: "paused" }),
];

test("deactivated accounts and the Resume action", async ({ page }) => {
  await mockApi(page, recoveryAccounts);
  await page.goto(`${BASE_URL}/dashboard`);
  await page.getByRole("radio", { name: "View accounts as list" }).click();
  const row = page.getByTestId("account-list-row").filter({ hasText: "Recovery account" });
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row.getByRole("button", { name: "Resume Recovery account", exact: true })).toHaveCount(before ? 0 : 1);
  await expect(page.getByRole("button", { name: "Resume Reauth account", exact: true })).toHaveCount(0);
  await shoot(page.getByTestId("dashboard-account-list"), "dashboard-list-1440");

  for (const width of [640, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("radio", { name: "View accounts as cards" }).click();
    const card = page.getByTestId("dashboard-account-cards").locator(":scope > div").filter({ hasText: "Recovery account" });
    await expect(card).toBeVisible();
    await expect(card.getByRole("button", { name: "Resume", exact: true })).toHaveCount(before ? 0 : 1);
    await shoot(page.getByTestId("dashboard-account-cards"), `dashboard-cards-${width}`);
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE_URL}/accounts?selected=acc_recover`);
  const detail = page.getByTestId("accounts-inline-detail");
  await expect(detail.getByText("Recovery account").first()).toBeVisible({ timeout: 15_000 });
  await expect(detail.getByRole("button", { name: "Resume", exact: true })).toHaveCount(before ? 0 : 1);
  await detail.getByRole("button", { name: "Re-authenticate", exact: true }).scrollIntoViewIfNeeded();
  await shoot(page, "accounts-deactivated-1440");
});
