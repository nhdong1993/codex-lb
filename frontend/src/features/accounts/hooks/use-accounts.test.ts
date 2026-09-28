import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { createElement, type PropsWithChildren } from "react";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import {
  useAccounts,
  useAccountMutations,
  useAccountUsageResetCredits,
} from "@/features/accounts/hooks/use-accounts";
import { useDashboard } from "@/features/dashboard/hooks/use-dashboard";
import type { AccountSummary } from "@/features/accounts/schemas";
import { createAccountSummary, createDashboardOverview } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("useAccounts", () => {
  it.each<{ name: string; updates: Partial<AccountSummary> }>([
    { name: "free plan", updates: { planType: "free", subscription: null } },
    { name: "different paid plan", updates: { planType: "pro", subscription: null } },
    { name: "ChatGPT identity", updates: { chatgptAccountId: "replacement", subscription: null } },
    { name: "email", updates: { email: "replacement@example.com", subscription: null } },
    { name: "workspace", updates: { workspaceId: "replacement", subscription: null } },
    { name: "legacy workspace label", updates: { workspaceLabel: "replacement", subscription: null } },
    { name: "credential refresh", updates: { lastRefreshAt: "2026-09-28T13:00:00Z", subscription: null } },
    { name: "newer paid check", updates: { subscription: { activeUntil: "2026-11-04T00:00:00Z", lastCheckedAt: "2026-09-28T13:00:00Z", source: "subscriptions_api" } } },
    { name: "newer inactive check", updates: { subscription: { activeUntil: null, lastCheckedAt: "2026-09-28T13:00:00Z", source: "subscriptions_api" } } },
  ])("rejects a delayed subscription response after a newer $name", async ({ updates }) => {
    const client = createTestQueryClient();
    const original = createAccountSummary({ accountId: "same-row", workspaceId: null, lastRefreshAt: "2026-09-27T00:00:00Z" });
    const response = createAccountSummary({ ...original, subscription: { activeUntil: "2026-10-04T00:00:00Z", lastCheckedAt: "2026-09-28T12:00:00Z", source: "subscriptions_api" } });
    const newer = createAccountSummary({ ...original, ...updates });
    let listed = original;
    const finish = deferred();
    let responseReady = false;
    server.use(
      http.get("/api/accounts", () => HttpResponse.json({ accounts: [listed] })),
      http.post("/api/accounts/same-row/subscription/refresh", async () => {
        responseReady = true;
        await finish.promise;
        return HttpResponse.json(response);
      }),
    );
    const { result } = renderHook(() => useAccounts(), { wrapper: createWrapper(client) });
    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));
    const refreshing = result.current.subscriptionRefreshMutation.mutateAsync("same-row");
    await waitFor(() => expect(responseReady).toBe(true));
    listed = newer;
    await act(async () => { await result.current.accountsQuery.refetch(); });
    await waitFor(() => expect(result.current.accountsQuery.data?.[0]).toEqual(newer));
    await act(async () => { finish.resolve(); await refreshing; });
    await waitFor(() => expect(result.current.subscriptionRefreshMutation.isSuccess).toBe(true));
    expect(result.current.accountsQuery.data?.[0]).toEqual(newer);
  });

  it("merges a matching fresh subscription while retaining concurrent unrelated changes", async () => {
    const client = createTestQueryClient();
    client.setQueryDefaults(["accounts", "list"], { gcTime: Infinity });
    const source = createAccountSummary({ accountId: "same-row", workspaceId: "workspace", workspaceLabel: "Before", lastRefreshAt: "2026-09-27T00:00:00Z", subscription: { activeUntil: null, lastCheckedAt: "2026-09-28T11:00:00Z", source: "subscriptions_api" } });
    const refreshed = createAccountSummary({ ...source, subscription: { activeUntil: "2026-10-04T00:00:00Z", lastCheckedAt: "2026-09-28T12:00:00Z", source: "subscriptions_api" } });
    const finish = deferred();
    server.use(http.post("/api/accounts/same-row/subscription/refresh", async () => {
      await finish.promise;
      return HttpResponse.json(refreshed);
    }));
    client.setQueryData(["accounts", "list"], { accounts: [source] });
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(client) });
    const refreshing = result.current.subscriptionRefreshMutation.mutateAsync("same-row");
    await waitFor(() => expect(result.current.subscriptionRefreshMutation.isPending).toBe(true));
    const changed = { ...source, alias: "Renamed", workspaceLabel: "After", status: "paused", routingPolicy: "preserve", usage: { primaryRemainingPercent: 20, secondaryRemainingPercent: 30 } };
    client.setQueryData(["accounts", "list"], { accounts: [changed] });
    await act(async () => { finish.resolve(); await refreshing; });
    expect(client.getQueryData(["accounts", "list"])).toEqual({ accounts: [{ ...changed, subscription: refreshed.subscription }] });
  });

  it("keeps a successful subscription refresh when an older list read returns later", async () => {
    const client = createTestQueryClient();
    const target = createAccountSummary({ accountId: "target", subscription: { activeUntil: "2026-09-04T00:00:00Z", lastCheckedAt: null } });
    const refreshed = { ...target, subscription: { activeUntil: "2026-10-04T00:00:00Z", lastCheckedAt: "2026-09-28T00:00:00Z", source: "subscriptions_api" } };
    const finishRefresh = deferred();
    const finishPoll = deferred();
    let polling = false;
    let pollStarted = false;
    let current = target;
    server.use(
      http.get("/api/accounts", async () => {
        const snapshot = current;
        if (polling) {
          pollStarted = true;
          await finishPoll.promise;
        }
        return HttpResponse.json({ accounts: [snapshot] });
      }),
      http.post("/api/accounts/target/subscription/refresh", async () => {
        await finishRefresh.promise;
        return HttpResponse.json(refreshed);
      }),
    );
    const { result } = renderHook(() => useAccounts(), { wrapper: createWrapper(client) });
    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));
    const refresh = result.current.subscriptionRefreshMutation.mutateAsync("target");
    await waitFor(() => expect(result.current.subscriptionRefreshMutation.isPending).toBe(true));
    polling = true;
    const poll = result.current.accountsQuery.refetch();
    await waitFor(() => expect(pollStarted).toBe(true));
    await act(async () => { finishRefresh.resolve(); await refresh; });
    await act(async () => { finishPoll.resolve(); await poll; });
    expect(result.current.accountsQuery.data?.[0].subscription).toEqual(refreshed.subscription);
    polling = false;
    current = { ...target, status: "paused", planType: "free", subscription: null };
    await act(async () => { await result.current.accountsQuery.refetch(); });
    expect(result.current.accountsQuery.data?.[0]).toMatchObject(current);
  });

  it.each([false, true])("tracks each pending subscription independently when the second fails=%s", async (failSecond) => {
    const client = createTestQueryClient();
    const first = createAccountSummary({ accountId: "first" });
    const second = createAccountSummary({ accountId: "second" });
    const finishFirst = deferred();
    const finishSecond = deferred();
    server.use(
      http.get("/api/accounts", () => HttpResponse.json({ accounts: [first, second] })),
      http.post("/api/accounts/first/subscription/refresh", async () => {
        await finishFirst.promise;
        return HttpResponse.json(first);
      }),
      http.post("/api/accounts/second/subscription/refresh", async () => {
        await finishSecond.promise;
        return failSecond
          ? HttpResponse.json({ error: { code: "subscription_refresh_failed", message: "Refresh failed" } }, { status: 502 })
          : HttpResponse.json(second);
      }),
    );
    const { result } = renderHook(() => useAccounts(), { wrapper: createWrapper(client) });
    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));
    const a = result.current.subscriptionRefreshMutation.mutateAsync("first");
    const b = result.current.subscriptionRefreshMutation.mutateAsync("second").catch(() => null);
    await waitFor(() => expect(result.current.subscriptionRefreshingAccountIds).toEqual(["first", "second"]));
    await act(async () => { finishSecond.resolve(); await b; });
    await waitFor(() => expect(result.current.subscriptionRefreshingAccountIds).toEqual(["first"]));
    await act(async () => { finishFirst.resolve(); await a; });
    await waitFor(() => expect(result.current.subscriptionRefreshingAccountIds).toEqual([]));
  });

  it("refreshes only the target subscription and preserves cached data on failure", async () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryDefaults(["accounts", "list"], { gcTime: Infinity });
    const target = createAccountSummary({ accountId: "target", routingPolicy: "preserve" });
    const other = createAccountSummary({ accountId: "other" });
    const subscription = { activeUntil: "2026-10-04T04:36:34Z", lastCheckedAt: "2026-09-28T12:00:00Z", source: "subscriptions_api" };
    queryClient.setQueryData(["accounts", "list"], { accounts: [target, other] });
    server.use(http.post("/api/accounts/target/subscription/refresh", () => HttpResponse.json({ ...target, subscription })));
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
    await result.current.subscriptionRefreshMutation.mutateAsync("target");
    const saved = queryClient.getQueryData<{ accounts: typeof target[] }>(["accounts", "list"]);
    expect(saved?.accounts[0].subscription).toEqual(subscription);
    expect(saved?.accounts[0].routingPolicy).toBe("preserve");
    expect(saved?.accounts[1]).toEqual(other);
    server.use(http.post("/api/accounts/target/subscription/refresh", () => HttpResponse.json({ error: { code: "subscription_refresh_failed", message: "Refresh failed" } }, { status: 502 })));
    await expect(result.current.subscriptionRefreshMutation.mutateAsync("target")).rejects.toThrow();
    expect(queryClient.getQueryData(["accounts", "list"])).toEqual(saved);
  });
  it("loads accounts and invalidates related queries after mutations", async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    let usageResetBody: unknown;
    server.use(
      http.post("/api/accounts/:accountId/usage-reset-credits/consume", async ({ params, request }) => {
        const accountId = String(params.accountId);
        usageResetBody = await request.json();
        return HttpResponse.json({
          status: "reset",
          accountId,
          code: "reset",
          windowsReset: 2,
          usageWritten: true,
          primaryUsedPercentBefore: 99,
          primaryUsedPercentAfter: 1,
          secondaryUsedPercentBefore: 80,
          secondaryUsedPercentAfter: 1,
          accountStatusBefore: "rate_limited",
          accountStatusAfter: "active",
        });
      }),
    );
    const { result } = renderHook(() => useAccounts(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));
    const firstAccountId = result.current.accountsQuery.data?.[0]?.accountId;
    expect(firstAccountId).toBeTruthy();

    await result.current.pauseMutation.mutateAsync(firstAccountId as string);
    await result.current.resumeMutation.mutateAsync(firstAccountId as string);
    await result.current.probeMutation.mutateAsync({
      accountId: firstAccountId as string,
    });
    await result.current.usageResetMutation.mutateAsync({
      accountId: firstAccountId as string,
    });
    expect(usageResetBody).toEqual({
      redeemRequestId: expect.any(String),
    });
    const routingPolicyResult = await result.current.routingPolicyMutation.mutateAsync({
      accountId: firstAccountId as string,
      routingPolicy: "preserve",
    });
    expect(routingPolicyResult.routingPolicy).toBe("preserve");

    const imported = await result.current.importMutation.mutateAsync(
      new File(["{}"], "auth.json", { type: "application/json" }),
    );
    await result.current.deleteMutation.mutateAsync({ accountId: imported.accountId, deleteHistory: false });

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["accounts", "usage-reset-credits"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["accounts", "trends", firstAccountId],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["accounts", "usage-reset-credits", firstAccountId], exact: true,
      });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["dashboard", "overview"] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["dashboard", "projections"] });
    });
  });

  it("exports auth for an account without invalidating account queries", async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useAccounts(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));
    const firstAccountId = result.current.accountsQuery.data?.[0]?.accountId;
    expect(firstAccountId).toBeTruthy();

    await result.current.exportAuthMutation.mutateAsync(firstAccountId as string);

    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ["accounts", "trends"] });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ["accounts", "usage-reset-credits"] });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ["dashboard", "overview"] });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ["dashboard", "projections"] });
  });

  it("reuses the dashboard usage reset redemption id after a failed attempt", async () => {
    const queryClient = createTestQueryClient();
    const usageResetBodies: unknown[] = [];
    server.use(
      http.post("/api/accounts/:accountId/usage-reset-credits/consume", async ({ params, request }) => {
        const accountId = String(params.accountId);
        usageResetBodies.push(await request.json());
        if (usageResetBodies.length === 1) {
          return HttpResponse.json(
            {
              error: {
                code: "upstream_timeout",
                message: "Upstream response was lost",
              },
            },
            { status: 504 },
          );
        }
        return HttpResponse.json({
          status: "already_redeemed",
          accountId,
          code: "already_redeemed",
          windowsReset: 1,
          usageWritten: true,
          primaryUsedPercentBefore: 99,
          primaryUsedPercentAfter: 1,
          secondaryUsedPercentBefore: 80,
          secondaryUsedPercentAfter: 1,
          accountStatusBefore: "rate_limited",
          accountStatusAfter: "active",
        });
      }),
    );
    const { result } = renderHook(() => useAccounts(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));

    await expect(
      result.current.usageResetMutation.mutateAsync({ accountId: "acc_primary" }),
    ).rejects.toThrow("Upstream response was lost");
    await result.current.usageResetMutation.mutateAsync({ accountId: "acc_primary" });

    expect(usageResetBodies).toHaveLength(2);
    expect(usageResetBodies[0]).toEqual({
      redeemRequestId: expect.any(String),
    });
    expect(usageResetBodies[1]).toEqual(usageResetBodies[0]);
  });

  it("does not reuse a failed dashboard usage reset redemption id for another account", async () => {
    const queryClient = createTestQueryClient();
    const usageResetBodies: unknown[] = [];
    server.use(
      http.post("/api/accounts/:accountId/usage-reset-credits/consume", async ({ request }) => {
        usageResetBodies.push(await request.json());
        return HttpResponse.json(
          {
            error: {
              code: "upstream_timeout",
              message: "Upstream response was lost",
            },
          },
          { status: 504 },
        );
      }),
    );
    const { result } = renderHook(() => useAccounts(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.accountsQuery.isSuccess).toBe(true));

    await expect(
      result.current.usageResetMutation.mutateAsync({ accountId: "acc_primary" }),
    ).rejects.toThrow("Upstream response was lost");
    await expect(
      result.current.usageResetMutation.mutateAsync({ accountId: "acc_secondary" }),
    ).rejects.toThrow("Upstream response was lost");

    expect(usageResetBodies).toHaveLength(2);
    expect(usageResetBodies[0]).toEqual({
      redeemRequestId: expect.any(String),
    });
    expect(usageResetBodies[1]).toEqual({
      redeemRequestId: expect.any(String),
    });
    expect(usageResetBodies[1]).not.toEqual(usageResetBodies[0]);
  });

  it("does not permanently poll usage reset credits", async () => {
    const queryClient = createTestQueryClient();
    const accountId = "acc_primary";

    const { result } = renderHook(() => useAccountUsageResetCredits(accountId), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const query = queryClient.getQueryCache().find({
      queryKey: ["accounts", "usage-reset-credits", accountId],
    });
    const refetchInterval = (query?.options as { refetchInterval?: unknown } | undefined)
      ?.refetchInterval;
    expect(refetchInterval).toBeUndefined();
  });
});


describe("reset-credit targeted reconciliation", () => {
  it("excludes unsampled plan capacity from aggregate quota after reset", async () => {
    const queryClient = createTestQueryClient();
    const target = createAccountSummary({ accountId: "target", capacityCreditsPrimary: 100, remainingCreditsPrimary: 0 });
    const unsampled = createAccountSummary({ accountId: "unsampled", usage: null, capacityCreditsPrimary: 100, remainingCreditsPrimary: null });
    const overview = createDashboardOverview({ accounts: [target, unsampled] });
    overview.windows.primary.accounts = [
      { accountId: "target", capacityCredits: 100, remainingCredits: 0, remainingPercentAvg: 0 },
      { accountId: "unsampled", capacityCredits: 100, remainingCredits: 0, remainingPercentAvg: null },
    ];
    queryClient.setQueryData(["dashboard", "overview", "today"], overview);
    server.use(
      http.post("/api/accounts/target/rate-limit-reset-credits/consume", () =>
        HttpResponse.json({ outcome: "confirmed_reset", code: "reset", windowsReset: 1, redeemedAt: null })),
      http.get("/api/accounts/target/summary", () => HttpResponse.json({
        ...target, remainingCreditsPrimary: 100,
        usage: { ...target.usage, primaryRemainingPercent: 100 }, resetCreditFetchedAt: "2031-01-01T00:00:00Z",
      })),
    );
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
    await result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "target" });
    expect(queryClient.getQueryData(["dashboard", "overview", "today"])).toMatchObject({
      summary: { primaryWindow: { capacityCredits: 100, remainingCredits: 100, remainingPercent: 100 } },
    });
  });

  it("updates only the target in account and dashboard caches without fetching lists", async () => {
    const queryClient = createTestQueryClient();
    const target = createAccountSummary({ accountId: "target", availableResetCredits: 3, capacityCreditsPrimary: 200, remainingCreditsPrimary: 0 });
    const other = createAccountSummary({ accountId: "other", availableResetCredits: 2, capacityCreditsPrimary: 200, remainingCreditsPrimary: 100 });
    queryClient.setQueryData(["accounts", "list"], { accounts: [target, other] });
    const overview = createDashboardOverview({ accounts: [target, other] });
    overview.windows.primary.accounts = [target, other].map((account) => ({
      accountId: account.accountId, capacityCredits: account.capacityCreditsPrimary!,
      remainingCredits: account.remainingCreditsPrimary!,
      remainingPercentAvg: 100 * account.remainingCreditsPrimary! / account.capacityCreditsPrimary!,
    }));
    queryClient.setQueryData(["dashboard", "overview", "today"], overview);
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    let consumes = 0;
    let lists = 0;
    server.use(
      http.get("/api/accounts", () => { lists += 1; return HttpResponse.json({ accounts: [] }); }),
      http.post("/api/accounts/target/rate-limit-reset-credits/consume", () => {
        consumes += 1;
        return HttpResponse.json({ code: "reset", outcome: "confirmed_reset", windowsReset: 1, redeemedAt: null });
      }),
      http.get("/api/accounts/target/summary", () => HttpResponse.json({
        ...target, availableResetCredits: 2, remainingCreditsPrimary: 200, resetCreditFetchedAt: "2026-09-21T00:00:00Z",
      })),
    );
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
    await result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "target", redeemRequestId: "one" });
    const cached = queryClient.getQueryData<{ accounts: typeof target[] }>(["accounts", "list"]);
    expect(cached?.accounts[0].availableResetCredits).toBe(2);
    expect(cached?.accounts[1]).toBe(other);
    expect(queryClient.getQueryData(["dashboard", "overview", "today"])).toMatchObject({
      accounts: [{ accountId: "target", availableResetCredits: 2 }, { accountId: "other", availableResetCredits: 2 }],
      summary: { primaryWindow: { capacityCredits: 400, remainingCredits: 300, remainingPercent: 75 } },
      windows: { primary: { accounts: [{ accountId: "target", remainingCredits: 200 }, { accountId: "other", remainingCredits: 100 }] } },
    });
    expect(consumes).toBe(1);
    expect(lists).toBe(0);
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["accounts", "list"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["accounts", "reset-credits", "target"], exact: true });
  });
});


describe("reset-credit reconciliation failures", () => {
  it("keeps concurrent targets separate when one summary fails, without retrying consumption", async () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryDefaults(["accounts", "list"], { gcTime: Infinity });
    const first = createAccountSummary({ accountId: "first", availableResetCredits: 3 });
    const second = createAccountSummary({ accountId: "second", availableResetCredits: 2 });
    const other = createAccountSummary({ accountId: "other", availableResetCredits: 7 });
    queryClient.setQueryData(["accounts", "list"], { accounts: [first, second, other] });
    const consumed: string[] = [];
    const reads: string[] = [];
    server.use(
      http.post("/api/accounts/:id/rate-limit-reset-credits/consume", ({ params }) => {
        consumed.push(String(params.id));
        return HttpResponse.json({ code: "reset", outcome: "confirmed_reset", windowsReset: 1, redeemedAt: null });
      }),
      http.get("/api/accounts/:id/summary", ({ params }) => {
        reads.push(String(params.id));
        if (params.id === "first" && reads.filter((id) => id === "first").length === 1) {
          return HttpResponse.json({ error: { message: "Refresh unavailable", code: "unavailable" } }, { status: 503 });
        }
        return HttpResponse.json({
          ...(params.id === "first" ? first : second), availableResetCredits: 1,
          resetCreditFetchedAt: "2026-09-21T00:00:00Z",
        });
      }),
    );
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
    await act(async () => {
      await Promise.all([
        result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "first" }),
        result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "second" }),
      ]);
    });
    expect(consumed.sort()).toEqual(["first", "second"]);
    expect(reads.filter((id) => id === "first")).toHaveLength(2);
    const cached = queryClient.getQueryData<{ accounts: typeof first[] }>(["accounts", "list"]);
    expect(cached?.accounts.slice(0, 2).map((account) => account.availableResetCredits)).toEqual([1, 1]);
    expect(cached?.accounts[2]).toBe(other);
  });

  it.each(["no_reset", "unknown"])("never announces restored quota for %s", async (outcome) => {
    const queryClient = createTestQueryClient();
    const success = vi.spyOn(toast, "success");
    const info = vi.spyOn(toast, "info");
    success.mockClear();
    info.mockClear();
    server.use(
      http.post("/api/accounts/target/rate-limit-reset-credits/consume", () =>
        HttpResponse.json({ code: "nothing_to_reset", outcome, windowsReset: 0, redeemedAt: null })),
      http.get("/api/accounts/target/summary", () => HttpResponse.json(createAccountSummary({
        accountId: "target", resetCreditFetchedAt: "2026-09-21T00:00:00Z",
      }))),
    );
    const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
    await result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "target" });
    expect(success).not.toHaveBeenCalled();
    expect(info).toHaveBeenCalledWith(outcome === "no_reset"
      ? "The credit was redeemed, but no quota window was reset."
      : "Reset outcome is not confirmed. Check the account before trying again.");
  });
});


it("keeps a missing snapshot pending after four reads without repeating consume", async () => {
  const queryClient = createTestQueryClient();
  queryClient.setQueryDefaults(["accounts", "list"], { gcTime: Infinity });
  const target = createAccountSummary({ accountId: "pending", availableResetCredits: 3 });
  queryClient.setQueryData(["accounts", "list"], { accounts: [target] });
  let consumes = 0;
  let reads = 0;
  server.use(
    http.post("/api/accounts/pending/rate-limit-reset-credits/consume", () => {
      consumes += 1;
      return HttpResponse.json({ outcome: "confirmed_reset", code: "reset", windowsReset: 1, redeemedAt: null });
    }),
    http.get("/api/accounts/pending/summary", () => {
      reads += 1;
      return HttpResponse.json({ ...target, availableResetCredits: 0, resetCreditFetchedAt: null });
    }),
  );
  const { result } = renderHook(() => useAccountMutations(), { wrapper: createWrapper(queryClient) });
  await act(async () => { await result.current.resetCreditConsumeMutation.mutateAsync({ accountId: "pending" }); });
  expect(consumes).toBe(1);
  expect(reads).toBe(4);
  expect(queryClient.getQueryData(["accounts", "list"])).toMatchObject({
    accounts: [{ accountId: "pending", availableResetCredits: 3, resetCreditRefreshPending: true }],
  });
}, 10_000);

it("retains pending reset across account/dashboard polls and resolves with a fresh snapshot", async () => {
  const queryClient = createTestQueryClient();
  const target = createAccountSummary({ accountId: "pending", availableResetCredits: 3 });
  const other = createAccountSummary({ accountId: "other" });
  let polled = target;
  let consumes = 0;
  server.use(
    http.get("/api/accounts", () => HttpResponse.json({ accounts: [polled, other] })),
    http.get("/api/dashboard/overview", () => HttpResponse.json(createDashboardOverview({ accounts: [polled, other] }))),
    http.post("/api/accounts/pending/rate-limit-reset-credits/consume", () => {
      consumes += 1;
      return HttpResponse.json({ outcome: "confirmed_reset", code: "reset", windowsReset: 1, redeemedAt: null });
    }),
    http.get("/api/accounts/pending/summary", () => HttpResponse.json({ ...target, resetCreditFetchedAt: null })),
  );
  const { result } = renderHook(() => ({ accounts: useAccounts(), dashboard: useDashboard() }), { wrapper: createWrapper(queryClient) });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.isSuccess).toBe(true);
    expect(result.current.dashboard.isSuccess).toBe(true);
  });
  await act(async () => {
    await result.current.accounts.resetCreditConsumeMutation.mutateAsync({ accountId: "pending" });
    polled = { ...target, availableResetCredits: 0, resetCreditFetchedAt: null };
    await Promise.all([result.current.accounts.accountsQuery.refetch(), result.current.dashboard.refetch()]);
  });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.data?.[0].resetCreditRefreshPending).toBe(true);
    expect(result.current.dashboard.data?.accounts[0].resetCreditRefreshPending).toBe(true);
  });
  polled = { ...target, availableResetCredits: 2, resetCreditFetchedAt: "2031-01-01T00:00:00Z" };
  await act(async () => {
    await Promise.all([result.current.accounts.accountsQuery.refetch(), result.current.dashboard.refetch()]);
  });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.data?.[0].resetCreditRefreshPending).toBe(false);
    expect(result.current.dashboard.data?.accounts[0].resetCreditRefreshPending).toBe(false);
    expect(result.current.accounts.accountsQuery.data?.[1].resetCreditRefreshPending).toBeUndefined();
  });
  expect(consumes).toBe(1);
  polled = { ...target, status: "paused", availableResetCredits: 0, resetCreditFetchedAt: null };
  await act(async () => {
    await Promise.all([result.current.accounts.accountsQuery.refetch(), result.current.dashboard.refetch()]);
  });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.data?.[0]).toMatchObject({
      status: "paused", availableResetCredits: 0, resetCreditRefreshPending: false,
    });
    expect(result.current.dashboard.data?.accounts[0]).toMatchObject({
      status: "paused", availableResetCredits: 0, resetCreditRefreshPending: false,
    });
  });
}, 12_000);

it("rejects poll responses that started before a newer targeted summary", async () => {
  const queryClient = createTestQueryClient();
  const target = createAccountSummary({ accountId: "target", availableResetCredits: 3, resetCreditFetchedAt: "2030-01-01T00:00:00Z" });
  let blocked = false;
  let started = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  server.use(
    http.get("/api/accounts", async () => {
      if (blocked) { started += 1; await gate; }
      return HttpResponse.json({ accounts: [target] });
    }),
    http.get("/api/dashboard/overview", async () => {
      if (blocked) { started += 1; await gate; }
      return HttpResponse.json(createDashboardOverview({ accounts: [target] }));
    }),
    http.post("/api/accounts/target/rate-limit-reset-credits/consume", () =>
      HttpResponse.json({ outcome: "confirmed_reset", code: "reset", windowsReset: 1, redeemedAt: null })),
    http.get("/api/accounts/target/summary", () => HttpResponse.json({
      ...target, availableResetCredits: 2, resetCreditFetchedAt: "2031-01-01T00:00:00Z",
    })),
  );
  const { result } = renderHook(() => ({ accounts: useAccounts(), dashboard: useDashboard() }), { wrapper: createWrapper(queryClient) });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.isSuccess).toBe(true);
    expect(result.current.dashboard.isSuccess).toBe(true);
  });
  blocked = true;
  const polling = Promise.all([result.current.accounts.accountsQuery.refetch(), result.current.dashboard.refetch()]);
  try {
    await waitFor(() => expect(started).toBe(2));
    await act(async () => { await result.current.accounts.resetCreditConsumeMutation.mutateAsync({ accountId: "target" }); });
  } finally {
    release();
    await act(async () => { await polling; });
  }
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.data?.[0].availableResetCredits).toBe(2);
    expect(result.current.dashboard.data?.accounts[0].availableResetCredits).toBe(2);
  });
});

it("keeps a refreshed subscription when a delayed usage reset summary arrives", async () => {
  const queryClient = createTestQueryClient();
  const original = createAccountSummary({
    accountId: "target",
    subscription: {
      activeUntil: "2026-09-04T00:00:00Z",
      lastCheckedAt: "2026-08-28T00:00:00Z",
      source: "id_token",
    },
  });
  const refreshed = {
    ...original,
    subscription: {
      activeUntil: "2026-10-04T00:00:00Z",
      lastCheckedAt: "2026-09-28T00:00:00Z",
      source: "subscriptions_api" as const,
    },
  };
  const summaryGate = deferred();
  let summaryStarted = false;
  server.use(
    http.get("/api/accounts", () => HttpResponse.json({ accounts: [original] })),
    http.get("/api/dashboard/overview", () => HttpResponse.json(createDashboardOverview({ accounts: [original] }))),
    http.post("/api/accounts/target/subscription/refresh", () => HttpResponse.json(refreshed)),
    http.post("/api/accounts/target/usage-reset-credits/consume", () => HttpResponse.json({
      status: "reset", accountId: "target", code: "reset", windowsReset: 2, usageWritten: true,
      primaryUsedPercentBefore: 99, primaryUsedPercentAfter: 1,
      secondaryUsedPercentBefore: 80, secondaryUsedPercentAfter: 1,
      accountStatusBefore: "rate_limited", accountStatusAfter: "active",
    })),
    http.get("/api/accounts/target/summary", async () => {
      summaryStarted = true;
      await summaryGate.promise;
      return HttpResponse.json({
        ...original,
        usage: { primaryRemainingPercent: 99, secondaryRemainingPercent: 99 },
      });
    }),
  );
  const { result } = renderHook(() => ({ accounts: useAccounts(), dashboard: useDashboard() }), {
    wrapper: createWrapper(queryClient),
  });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.isSuccess).toBe(true);
    expect(result.current.dashboard.isSuccess).toBe(true);
  });
  const reset = result.current.accounts.usageResetMutation.mutateAsync({ accountId: "target" });
  await waitFor(() => expect(summaryStarted).toBe(true));
  await act(async () => { await result.current.accounts.subscriptionRefreshMutation.mutateAsync("target"); });
  await waitFor(() => expect(result.current.accounts.accountsQuery.data?.[0].subscription).toEqual(refreshed.subscription));
  await act(async () => {
    summaryGate.resolve();
    await reset;
  });
  await waitFor(() => {
    expect(result.current.accounts.accountsQuery.data?.[0].usage?.primaryRemainingPercent).toBe(99);
    expect(result.current.dashboard.data?.accounts[0].usage?.primaryRemainingPercent).toBe(99);
  });
  expect(result.current.accounts.accountsQuery.data?.[0].subscription).toEqual(refreshed.subscription);
  expect(result.current.dashboard.data?.accounts[0].subscription).toEqual(refreshed.subscription);
  await act(async () => {
    await Promise.all([result.current.accounts.accountsQuery.refetch(), result.current.dashboard.refetch()]);
  });
  expect(result.current.accounts.accountsQuery.data?.[0].subscription).toEqual(refreshed.subscription);
  expect(result.current.dashboard.data?.accounts[0].subscription).toEqual(refreshed.subscription);
});
