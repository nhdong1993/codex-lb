import { expect, test, type Route } from "@playwright/test";
import path from "node:path";
import type { AccountSummary } from "../src/features/accounts/schemas";

import {
  accounts,
  accountTrends,
  authSession,
  overview,
  settings,
  upstreamProxyAdmin,
} from "./fixtures";

const directory = process.env.ACCOUNT_GRID_SCREENSHOTS;
const sampleTime = Date.parse("2026-09-27T12:00:00Z");
const at = (minutes: number) =>
  new Date(sampleTime + minutes * 60_000).toISOString();
const sampleAccounts = accounts.map((account, index) => ({
  ...account,
  email: `account-${index + 1}@example.com`,
  alias: [
    "Personal Plus",
    "Research Pro",
    "Team workspace",
    "Build runner",
    "Backup Plus",
    "Design tools",
    "Development",
  ][index],
  displayName: [
    "Personal Plus",
    "Research Pro",
    "Team workspace",
    "Build runner",
    "Backup Plus",
    "Design tools",
    "Development",
  ][index],
  workspaceLabel: index === 2 ? "Product Team" : "Personal workspace",
  seatType: index === 2 ? "owner" : null,
  planType: index === 1 ? "pro" : index === 2 ? "team" : index === 3 ? "prolite" : index === 5 ? "promax" : "plus",
  status: index === 4 ? "paused" : "active",
  routingPolicy:
    index === 0 ? "burn_first" : index === 4 ? "preserve" : "normal",
  limitWarmupEnabled: index < 3,
  securityWorkAuthorized: index === 1,
  usage: {
    primaryRemainingPercent: [86, 64, 94, 47, 100, 14, 82][index],
    secondaryRemainingPercent: [72, 48, 90, 28, 100, 3, 62][index],
  },
  resetAtPrimary: at(126 + index * 12),
  resetAtSecondary: at((3 + index) * 24 * 60),
  lastRefreshAt: at(-18 - index * 9),
  creditsBalance: index === 1 ? 250 : 0,
  requestUsage: {
    requestCount: 1248 - index * 150,
    totalTokens: 8_400_000 - index * 800_000,
    cachedInputTokens: 3_100_000 - index * 400_000,
    totalCostUsd: 18.42 - index * 2.15,
  },
  auth: {
    access: { expiresAt: at(540) },
    refresh: { state: "stored" },
    idToken: { state: "parsed" },
  },
  subscription: {
    activeUntil:
      index === 2
        ? null
        : index === 3
          ? at(32 * 60)
          : index === 5
            ? at(-2 * 24 * 60)
            : at((18 - index) * 24 * 60 + 8 * 60),
    lastCheckedAt: at(-180),
    source: "subscriptions_api" as const,
  },
}));

for (const language of ["en", "ko", "zh-CN"]) {
  test(`List badges wrap on narrow phones (${language})`, async ({ page }) => {
    await page.clock.setFixedTime(new Date(sampleTime));
    await page.emulateMedia({ reducedMotion: "reduce" });
    const fleet = ["enterprise", "plus", "free"].map((planType, index) => ({
      ...sampleAccounts[index], planType, status: "reauth_required", availableResetCredits: 12,
    }));
    let showResetCreditBadges = true;
    await page.addInitScript(() => localStorage.setItem("codex-lb-accounts-view-mode", "list"));
    await page.route("**/api/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      return route.fulfill({ json: pathname === "/api/dashboard-auth/session" ? authSession
        : pathname === "/api/accounts" ? { accounts: fleet }
        : pathname === "/api/settings" ? { ...settings, showResetCreditBadges }
        : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin : {} });
    });
    await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}/accounts?lang=${language}`);
    const rows = page.getByTestId("account-list-overview-row");
    await expect(rows).toHaveCount(3);
    for (const width of [320, 375, 390, 1024]) {
      await page.setViewportSize({ width, height: 1000 });
      const collisions = await rows.evaluateAll((items) => items.flatMap((row) => {
        const badges = ["plan", "status", "reset"].map((name) => row.querySelector(`[data-testid="account-list-${name}-cell"] [data-slot="badge"]`)!.getBoundingClientRect());
        return badges.flatMap((left, i) => badges.slice(i + 1).filter((right) =>
          Math.min(left.right, right.right) > Math.max(left.left, right.left) &&
          Math.min(left.bottom, right.bottom) > Math.max(left.top, right.top),
        ).map(() => row.textContent));
      }));
      expect(collisions).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (directory && width === 320) await page.screenshot({ path: path.join(directory, `list-narrow-${language}.png`), animations: "disabled" });
    }
    await page.setViewportSize({ width: 320, height: 1000 });
    const badge = await rows.first().getByTestId("account-list-plan-cell").boundingBox();
    expect(badge).not.toBeNull();
    await page.mouse.click(badge!.x + badge!.width / 2, badge!.y + badge!.height / 2);
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    showResetCreditBadges = false;
    await page.setViewportSize({ width: 320, height: 1000 });
    await page.reload();
    await expect(rows).toHaveCount(3);
    await expect(page.getByTestId("account-list-reset-cell")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("List quota sorting is separate from mixed-plan quota data", async ({ page }) => {
  await page.clock.setFixedTime(new Date(sampleTime));
  await page.emulateMedia({ reducedMotion: "reduce" });
  const fleet = [sampleAccounts[0], {
    ...sampleAccounts[1], planType: "free", subscription: null,
    usage: { primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: 25 },
    windowMinutesPrimary: null, windowMinutesSecondary: null, windowMinutesMonthly: 43200,
    resetAtPrimary: null, resetAtSecondary: null, resetAtMonthly: at(20 * 24 * 60),
  }];
  await page.addInitScript(() => localStorage.setItem("codex-lb-accounts-view-mode", "list"));
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    return route.fulfill({ json: pathname === "/api/dashboard-auth/session" ? authSession
      : pathname === "/api/accounts" ? { accounts: fleet }
      : pathname === "/api/settings" ? settings
      : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin : {} });
  });
  await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}/accounts`);
  const rows = page.getByTestId("account-list-overview-row");
  for (const preference of ["both", "5h", "weekly"]) {
    await page.evaluate((value) => localStorage.setItem("codex-lb-account-quota-display", value), preference);
    await page.reload();
    await expect(rows).toHaveCount(2);
    for (const width of [1440, 1024]) {
      await page.setViewportSize({ width, height: 1000 });
      const sorts = page.getByRole("group", { name: "Sort quota", exact: true });
      const headers = page.getByTestId("account-list-column-headers");
      await expect(sorts).toBeVisible();
      await expect(headers.getByText("Quota remaining", { exact: true })).toBeVisible();
      await expect(headers.getByRole("button", { name: /^(Quota 5h|Quota 7d|Monthly):/ })).toHaveCount(0);
      const bounds = await sorts.boundingBox();
      const headerBounds = await headers.boundingBox();
      expect(bounds && headerBounds && bounds.y + bounds.height <= headerBounds.y).toBeTruthy();
      for (const label of ["Quota 5h", "Quota 7d", "Monthly"]) {
        await sorts.getByRole("button", { name: `${label}: Not sorted`, exact: true }).click();
        await expect(sorts.getByRole("button", { name: `${label}: Ascending`, exact: true })).toHaveAttribute("aria-pressed", "true");
      }
      // Each viewport starts its next pass on a non-quota sort.
      await headers.getByRole("button", { name: /^Status:/ }).click();
      const free = rows.filter({ hasText: "Research Pro" });
      await expect(free.getByTestId("list-overview-quota-Monthly")).toBeVisible();
      await expect(free.getByTestId("list-overview-quota-5h")).toHaveCount(0);
      if (directory && width === 1440) await page.screenshot({ path: path.join(directory, `list-quota-${preference}.png`), animations: "disabled" });
    }
  }
});

test("List separates sortable Status and Reset and sorts monthly Free quota", async ({ page }) => {
  const fleet = sampleAccounts.map((account, index) => index < 4 ? {
    ...account,
    planType: "free",
    subscription: null,
    status: ["active", "paused", "reauth_required", "rate_limited"][index],
    usage: { primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: [0, 90, null, 25][index] },
    windowMinutesPrimary: null, windowMinutesSecondary: null, windowMinutesMonthly: 43200,
    resetAtPrimary: null, resetAtSecondary: null, resetAtMonthly: at(20 * 24 * 60),
    availableResetCredits: [0, 12, null, 3][index],
  } : account);
  let showResetCreditBadges = true;
  await page.addInitScript(() => localStorage.setItem("codex-lb-accounts-view-mode", "list"));
  await page.clock.setFixedTime(new Date(sampleTime));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const data = pathname === "/api/dashboard-auth/session" ? authSession
      : pathname === "/api/settings" ? { ...settings, showResetCreditBadges }
      : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
      : pathname === "/api/accounts" ? { accounts: fleet }
      : {};
    return route.fulfill({ json: data });
  });
  await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}/accounts`);
  const rows = page.getByTestId("account-list-overview-row");
  await expect(rows).toHaveCount(fleet.length);
  await page.getByRole("button", { name: "Status: Not sorted", exact: true }).click();
  await expect(rows.first().getByTestId("account-list-status-cell")).toHaveText("Active");
  await page.getByRole("button", { name: "Status: Ascending", exact: true }).click();
  await expect(rows.first().getByTestId("account-list-status-cell")).toHaveText("Re-auth required");
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const heights = await rows.evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height));
    expect(Math.max(...heights)).toBeLessThanOrEqual(width >= 1024 ? 80 : 180);
    if (width >= 1024) {
      for (const [label, cellId] of [["Status", "account-list-status-cell"], ["Reset", "account-list-reset-cell"]]) {
        const header = await page.getByRole("button", { name: new RegExp(`^${label}:`) }).boundingBox();
        const cell = await rows.first().getByTestId(cellId).boundingBox();
        expect(header && cell && Math.abs(header.x - cell.x) < 2).toBeTruthy();
      }
      const plan = await rows.first().getByTestId("account-list-plan-cell").boundingBox();
      const status = await rows.first().getByTestId("account-list-status-cell").locator("[data-slot=badge]").boundingBox();
      const reset = await rows.first().getByTestId("account-list-reset-cell").boundingBox();
      expect(plan && status && reset && plan.x + plan.width <= status.x && status.x + status.width <= reset.x).toBeTruthy();
    }
    if (directory) await page.screenshot({ path: path.join(directory, `list-mixed-${width}.png`), animations: "disabled" });
  }
  await page.getByRole("combobox", { name: "Sort accounts" }).click();
  await page.getByRole("option", { name: "Reset credits (fewest first)", exact: true }).click();
  await expect(rows.first().getByTestId("account-list-reset-cell")).toHaveText("Reset (0)");
  await expect(rows.last().getByTestId("account-list-reset-cell")).toHaveText("—");
  await page.getByRole("combobox", { name: "Filter accounts by plan" }).click();
  await page.getByRole("option", { name: "Free", exact: true }).click();
  await expect(rows).toHaveCount(4);
  await page.getByRole("combobox", { name: "Sort accounts" }).click();
  await page.getByRole("option", { name: "Monthly quota (lowest remaining)", exact: true }).click();
  await expect(rows.first()).toContainText("Personal Plus");
  await expect(rows.last()).toContainText("Team workspace");
  await expect(page.getByTestId("list-overview-quota-Monthly")).toHaveCount(4);
  await expect(page.getByTestId("list-overview-quota-5h")).toHaveCount(0);
  if (directory) await page.screenshot({ path: path.join(directory, "list-free-mobile.png"), animations: "disabled" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Monthly: Ascending", exact: true }).click();
  await expect(rows.first()).toContainText("Research Pro");
  await expect(rows.last()).toContainText("Team workspace");
  if (directory) await page.screenshot({ path: path.join(directory, "list-free-desktop.png"), animations: "disabled" });
  showResetCreditBadges = false;
  await page.reload();
  await expect(page.getByTestId("account-list-reset-cell")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Reset:/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Status:/ })).toBeVisible();
  if (directory) await page.screenshot({ path: path.join(directory, "list-without-reset-desktop.png"), animations: "disabled" });
});

test("A delayed subscription response does not restore a paid term after the plan changes", async ({ page }) => {
  const liveAccounts = structuredClone(sampleAccounts).map((account) => ({
    ...account, subscription: account.subscription as AccountSummary["subscription"],
  }));
  const paidResponse = structuredClone(liveAccounts[0]);
  let pending: Route | undefined;
  await page.addInitScript(() => localStorage.setItem("codex-lb-accounts-view-mode", "list"));
  await page.clock.install({ time: new Date(sampleTime) });
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/subscription/refresh")) {
      pending = route;
      return;
    }
    const data = pathname === "/api/dashboard-auth/session" ? authSession
      : pathname === "/api/settings" ? settings
      : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
      : pathname === "/api/accounts" ? { accounts: liveAccounts }
      : {};
    return route.fulfill({ json: data });
  });
  await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}/accounts`);
  const row = page.getByTestId("account-list-overview-row").filter({ hasText: "Personal Plus" });
  const refresh = row.getByRole("button", { name: "Refresh subscription for Personal Plus", exact: true });
  await refresh.click();
  await expect.poll(() => pending != null).toBe(true);
  liveAccounts[0].planType = "free";
  liveAccounts[0].subscription = null;
  await page.clock.fastForward(31_000);
  await expect(row.getByText("Free", { exact: true })).toBeVisible();
  await expect(row.getByTestId("account-plan-remaining")).toHaveText("No data");
  await pending!.fulfill({ json: paidResponse });
  await expect(refresh.locator("svg")).not.toHaveClass(/animate-spin/);
  if (directory) await page.screenshot({ path: path.join(directory, "list-delayed-paid-response.png"), animations: "disabled" });
  await expect(row.getByTestId("account-plan-remaining")).toHaveText("No data");
});

test("Subscription refresh keeps each account pending until its own request settles", async ({ page }) => {
  const pending = new Map<string, Route>();
  const first = sampleAccounts[0];
  const second = sampleAccounts[1];
  await page.addInitScript(() => localStorage.setItem("codex-lb-accounts-view-mode", "list"));
  await page.clock.setFixedTime(new Date(sampleTime));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/subscription/refresh")) {
      pending.set(pathname.split("/")[3], route);
      return;
    }
    const data = pathname === "/api/dashboard-auth/session" ? authSession
      : pathname === "/api/settings" ? settings
      : pathname === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
      : pathname === "/api/accounts" ? { accounts: sampleAccounts }
      : pathname.endsWith("/trends") ? accountTrends
      : pathname.endsWith("/usage-reset-credits") ? { rateLimitResetCredits: { availableCount: 3 } }
      : {};
    return route.fulfill({ json: data });
  });
  await page.goto(`http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}/accounts`);
  const a = page.getByRole("button", { name: "Refresh subscription for Personal Plus", exact: true });
  const b = page.getByRole("button", { name: "Refresh subscription for Research Pro", exact: true });
  await a.click();
  await b.click();
  await expect.poll(() => pending.size).toBe(2);
  if (directory) await page.screenshot({ path: path.join(directory, "list-two-refreshes-pending.png"), animations: "disabled" });
  await expect(a).toBeDisabled();
  await expect(b).toBeDisabled();
  await pending.get(second.accountId)!.fulfill({
    status: 502,
    json: { error: { code: "subscription_refresh_failed", message: "Refresh failed" } },
  });
  await expect(b).toBeEnabled();
  await expect(a).toBeDisabled();
  if (directory) await page.screenshot({ path: path.join(directory, "list-first-refresh-still-pending.png"), animations: "disabled" });
  await page.getByRole("button", { name: "View details for Personal Plus", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("button", { name: "Refresh subscription for Personal Plus", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Grid view", exact: true }).click();
  await expect(a).toBeDisabled();
  await page.getByRole("button", { name: "Detail view", exact: true }).click();
  await expect(a).toBeDisabled();
  await pending.get(first.accountId)!.fulfill({ json: first });
  await expect(a).toBeEnabled();
});

for (const mode of ["detail", "list", "grid"] as const) {
  test(`Accounts ${mode} overview fits desktop and mobile and opens account management`, async ({
    page,
  }) => {
    const managementRequests: string[] = [];
    const liveAccounts = structuredClone(sampleAccounts);
    const writes: string[] = [];
    if (mode !== "detail") {
      await page.addInitScript(
        (storedMode) =>
          localStorage.setItem("codex-lb-accounts-view-mode", storedMode),
        mode,
      );
    }
    await page.clock.setFixedTime(new Date(sampleTime));
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/**", (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (
        pathname.endsWith("/trends") ||
        pathname.endsWith("/usage-reset-credits")
      )
        managementRequests.push(pathname);
      if (pathname.endsWith("/routing-policy")) {
        const account = liveAccounts.find((item) => item.accountId === pathname.split("/")[3])!;
        account.routingPolicy = route.request().postDataJSON().routingPolicy;
        writes.push(pathname);
        return route.fulfill({ json: { accountId: account.accountId, routingPolicy: account.routingPolicy } });
      }
      if (pathname.endsWith("/subscription/refresh")) {
        const account = liveAccounts.find((item) => item.accountId === pathname.split("/")[3])!;
        writes.push(pathname);
        return route.fulfill({ json: account });
      }
      const data =
        pathname === "/api/dashboard-auth/session"
          ? authSession
          : pathname === "/api/settings"
            ? settings
            : pathname === "/api/settings/upstream-proxy"
              ? upstreamProxyAdmin
              : pathname === "/api/dashboard/overview"
                ? overview
                : pathname === "/api/accounts"
                  ? { accounts: liveAccounts }
                  : pathname.endsWith("/trends")
                    ? accountTrends[pathname.split("/")[3]]
                    : pathname.endsWith("/usage-reset-credits")
                      ? {
                          accountId: pathname.split("/")[3],
                          rateLimitResetCredits: { availableCount: 2 },
                        }
                      : null;
      return data ? route.fulfill({ json: data }) : route.abort();
    });
    const baseUrl =
      process.env.SCREENSHOT_BASE_URL ??
      `http://localhost:${process.env.SCREENSHOT_PORT ?? "4173"}`;
    await page.goto(`${baseUrl}/accounts`);
    const items =
      mode === "detail"
        ? page.getByTestId("account-list-scroll-region").getByRole("button")
        : page.getByTestId(
            mode === "grid" ? "account-grid-card" : "account-list-overview-row",
          );
    await expect(items).toHaveCount(sampleAccounts.length);
    await page.waitForLoadState("networkidle");
    if (mode === "detail") {
      await expect(page.getByTestId("accounts-inline-detail")).toBeVisible();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      expect(managementRequests.length).toBeGreaterThan(0);
      expect(managementRequests.every((url) => url.includes("/acc_01/"))).toBe(
        true,
      );
      await expect(
        page
          .getByTestId("accounts-inline-detail")
          .locator(".recharts-area-curve")
          .first(),
      ).toBeVisible();
    } else expect(managementRequests).toEqual([]);
    if (mode === "detail") {
      await expect(
        items.first().getByTestId("account-plan-remaining"),
      ).toHaveText("18d 8h");
      const status = await items
        .first()
        .getByText("Active", { exact: true })
        .boundingBox();
      const remaining = await items
        .first()
        .getByTestId("account-plan-remaining")
        .boundingBox();
      expect(
        status && remaining && remaining.y >= status.y + status.height,
      ).toBeTruthy();
    }
    if (mode === "list") {
      await expect(
        items.first().getByTestId("account-plan-remaining"),
      ).toHaveText("18d 8h");
      await expect(
        items
          .first()
          .getByText(
            /requests|tokens|Stored|Parsed|Token refreshed|Warm-up|Last checked|Recorded end date/i,
          ),
      ).toHaveCount(0);
      await expect(
        items.first().getByText("Reset (3)", { exact: true }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: "Plan: Not sorted", exact: true })
        .click();
      await expect(items.last()).toContainText("Team workspace");
      await page
        .getByRole("button", { name: "Plan: Ascending", exact: true })
        .click();
      await expect(items.first()).toContainText("Team workspace");
      await page
        .getByRole("button", { name: "Subscription: Not sorted", exact: true })
        .click();
      await expect(items.first()).toContainText("Design tools");
      await expect(items.last()).toContainText("Team workspace");
      await page
        .getByRole("button", { name: "Subscription: Ascending", exact: true })
        .click();
      await expect(items.first()).toContainText("Personal Plus");
      await expect(items.last()).toContainText("Team workspace");
      const weekly = page.getByRole("button", {
        name: "Quota 7d: Not sorted",
        exact: true,
      });
      await weekly.focus();
      await page.keyboard.press("Enter");
      await expect(items.first()).toContainText("Design tools");
      await page.keyboard.press("Enter");
      await expect(items.first()).toContainText("Backup Plus");
      await page
        .getByRole("button", { name: "Quota 5h: Not sorted", exact: true })
        .click();
      await expect(items.first()).toContainText("Design tools");
      await page
        .getByRole("button", { name: "Quota 5h: Ascending", exact: true })
        .click();
      await expect(items.first()).toContainText("Backup Plus");
      await expect(
        page.getByRole("combobox", { name: "Sort accounts" }),
      ).toHaveText("5h quota (highest remaining)");
    }
    await page.getByRole("combobox", { name: "Filter accounts by plan" }).click();
    await page.getByRole("option", { name: "Prolite", exact: true }).click();
    await expect(items).toHaveCount(1);
    await expect(items.first()).toContainText("Build runner");
    await page.getByRole("combobox", { name: "Filter accounts by plan" }).click();
    await page.getByRole("option", { name: "All plans", exact: true }).click();
    await expect(items).toHaveCount(sampleAccounts.length);
    if (mode === "list") {
      const toggle = page.getByRole("button", { name: "Toggle Burn First for Personal Plus", exact: true });
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      await toggle.click();
      await expect(toggle).toHaveAttribute("aria-pressed", "false");
      await toggle.click();
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      await page.getByRole("button", { name: "Refresh subscription for Personal Plus", exact: true }).click();
      await expect.poll(() => writes.length).toBe(3);
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.locator("[data-sonner-toast]")).toHaveCount(0, { timeout: 10000 });
    }
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({
        width,
        height:
          mode === "detail"
            ? width === 390
              ? 1050
              : 1500
            : width === 390
              ? 1050
              : 1000,
      });
      await expect.poll(
        () => page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      // Compact selector badges intentionally extend 4px past their row.
      if (mode !== "detail")
        expect(
          await items.evaluateAll((elements) =>
            elements.every(
              (element) => element.scrollWidth <= element.clientWidth,
            ),
          ),
        ).toBe(true);
      if (mode === "list") {
        const heights = await items.evaluateAll((rows) =>
          rows.map((row) => row.getBoundingClientRect().height),
        );
        expect(Math.max(...heights)).toBeLessThanOrEqual(
          width >= 1024 ? 80 : 180,
        );
      }
      if (mode === "detail" && width >= 1024) {
        const left = await page
          .getByTestId("accounts-list-panel")
          .boundingBox();
        const right = await page
          .getByTestId("accounts-inline-detail")
          .boundingBox();
        expect(left && right && left.x + left.width <= right.x).toBeTruthy();
      }
      if (directory && (width === 1440 || width === 390)) {
        if (mode === "detail") {
          await expect(
            page
              .getByTestId("accounts-inline-detail")
              .locator(".recharts-area-curve")
              .first(),
          ).toBeVisible();
        }
        await page.screenshot({
          path: path.join(
            directory,
            `${mode}-${width === 1440 ? "desktop" : "mobile"}.png`,
          ),
        });
      }
    }
    if (mode === "list" && directory) {
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.evaluate(() => document.documentElement.classList.add("dark"));
      await page.screenshot({ path: path.join(directory, "list-desktop-dark.png"), animations: "disabled" });
      await page.evaluate(() => document.documentElement.classList.remove("dark"));
      await page.setViewportSize({ width: 390, height: 1050 });
    }
    if (mode === "list") {
      await page.getByRole("combobox", { name: "Sort accounts" }).click();
      await expect(
        page.getByRole("option", {
          name: "Subscription (soonest)",
          exact: true,
        }),
      ).toBeVisible();
      if (directory)
        await page.screenshot({
          path: path.join(directory, "list-mobile-sort-menu.png"),
        });
      await page
        .getByRole("option", { name: "Subscription (soonest)", exact: true })
        .click();
      await expect(items.first()).toContainText("Design tools");
      await page
        .getByRole("button", { name: "Grid view", exact: true })
        .click();
      await expect(page.getByTestId("account-grid-card").first()).toContainText(
        "Design tools",
      );
      await page
        .getByRole("button", { name: "List view", exact: true })
        .click();
      await expect(items.first()).toContainText("Design tools");
      await expect(
        page.getByRole("combobox", { name: "Sort accounts" }),
      ).toHaveText("Subscription (soonest)");
    }
    if (mode === "detail") {
      await items.nth(1).click();
      await expect(
        page
          .getByTestId("accounts-inline-detail")
          .getByRole("heading", { name: "Research Pro", exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await page.reload();
      await expect(
        page.getByRole("button", { name: "Detail view", exact: true }),
      ).toHaveAttribute("aria-pressed", "true");
      await expect(
        page
          .getByTestId("accounts-inline-detail")
          .getByRole("heading", { name: "Research Pro", exact: true }),
      ).toBeVisible();
      return;
    }
    if (mode === "grid")
      await page
        .getByRole("button", { name: "View details", exact: true })
        .first()
        .click();
    else {
      await items.first().getByRole("button", { name: /^View details for/ }).focus();
      await page.keyboard.press("Enter");
    }
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    expect(
      await dialog.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    expect(new URL(page.url()).searchParams.has("selected")).toBe(false);
    managementRequests.length = 0;
    await page.reload();
    await expect(items).toHaveCount(sampleAccounts.length);
    await page.waitForLoadState("networkidle");
    expect(managementRequests).toEqual([]);
  });
}
