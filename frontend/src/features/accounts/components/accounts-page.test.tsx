import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AccountsPage } from "@/features/accounts/components/accounts-page";
import i18n from "@/i18n";
import { useAccountQuotaDisplayStore } from "@/hooks/use-account-quota-display";
import type { AccountSummary } from "@/features/accounts/schemas";

vi.mock("@/features/accounts/hooks/use-accounts", () => ({
  useAccounts: vi.fn(),
  useAccountTrends: vi.fn(() => ({ data: null })),
  useAccountUsageResetCredits: vi.fn(() => ({
    data: { rateLimitResetCredits: { availableCount: 3 } },
    isFetching: false,
    error: null,
  })),
}));

vi.mock("@/features/accounts/hooks/use-oauth", () => ({
  useOauth: vi.fn(() => ({
    state: {
      status: "idle",
      method: null,
      authorizationUrl: null,
      callbackUrl: null,
      verificationUrl: null,
      userCode: null,
      deviceAuthId: null,
      intervalSeconds: null,
      expiresInSeconds: null,
      errorMessage: null,
    },
    start: vi.fn(),
    complete: vi.fn(),
    manualCallback: vi.fn(),
    reset: vi.fn(),
  })),
}));

vi.mock("@/features/settings/hooks/use-settings", () => ({
  useSettings: vi.fn(() => ({
    settingsQuery: {
      data: {
        showResetCreditBadges: true,
        showResetCreditExpiryBadge: true,
      },
      error: null,
    },
  })),
  useUpstreamProxyAdmin: vi.fn(() => ({
    upstreamProxyQuery: { data: null, error: null },
    accountBindingMutation: {
      isPending: false,
      error: null,
      mutateAsync: vi.fn(),
    },
    testEndpointMutation: {
      isPending: false,
      error: null,
      mutateAsync: vi.fn(),
    },
  })),
}));

const { useAccounts } = await import("@/features/accounts/hooks/use-accounts");
const mockedUseAccounts = useAccounts as unknown as ReturnType<typeof vi.fn>;

function idleMutation() {
  return {
    isPending: false,
    error: null,
    mutateAsync: vi.fn(),
  };
}

function account(overrides: Partial<AccountSummary>): AccountSummary {
  return {
    accountId: "acc-default",
    email: "default@example.com",
    displayName: "Default",
    planType: "plus",
    status: "active",
    additionalQuotas: [],
    limitWarmupEnabled: false,
    ...overrides,
  };
}

function mockAccountsData(
  data: AccountSummary[] | undefined,
  error: Error | null = null,
  overrides: Record<string, unknown> = {},
) {
  mockedUseAccounts.mockReturnValue({
    accountsQuery: { data, error, refetch: vi.fn() },
    importMutation: idleMutation(),
    pauseMutation: idleMutation(),
    resumeMutation: idleMutation(),
    probeMutation: idleMutation(),
    usageResetMutation: idleMutation(),
    deleteMutation: idleMutation(),
    exportAuthMutation: idleMutation(),
    setAliasMutation: idleMutation(),
    limitWarmupMutation: idleMutation(),
    routingPolicyMutation: idleMutation(),
    subscriptionRefreshMutation: idleMutation(),
    subscriptionRefreshingAccountIds: [],
    updateMutation: idleMutation(),
    ...overrides,
  } as unknown as ReturnType<typeof useAccounts>);
}

describe("AccountsPage", () => {
  beforeEach(() => {
    window.localStorage.removeItem("codex-lb-accounts-view-mode");
    useAccountQuotaDisplayStore.setState({ quotaDisplay: "weekly" });
    vi.spyOn(Date, "now").mockReturnValue(
      new Date("2026-01-01T12:00:00.000Z").getTime(),
    );
  });

  afterEach(() => {
    window.localStorage.removeItem("codex-lb-accounts-view-mode");
    vi.restoreAllMocks();
  });

  it("counts normalized plans and unknown plans across the account inventory", () => {
    mockAccountsData([" Plus ", "PLUS", "prolite", " ", "custom_plan"].map((planType, index) =>
      account({ accountId: `plan-${index}`, planType }),
    ));

    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    const plans = within(screen.getByRole("region", { name: "Accounts by plan" }));
    expect(plans.getByTestId("donut-center-total")).toHaveTextContent(/^5$/);
    expect(plans.getAllByRole("button").map((row) => row.textContent)).toEqual([
      "Plus2 (40%)",
      "Unknown1 (20%)",
      "Custom plan1 (20%)",
      "Prolite1 (20%)",
    ]);
  });

  it("merges the backend unknown plan with blank plans into one translated bucket", async () => {
    mockAccountsData(["unknown", " Unknown ", " ", "plus"].map((planType, index) =>
      account({ accountId: `unknown-plan-${index}`, planType }),
    ));

    const view = render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    const plans = () => within(screen.getByRole("region", { name: "Accounts by plan" }));
    expect(plans().getAllByRole("button").map((row) => row.textContent)).toEqual([
      "Unknown3 (75%)",
      "Plus1 (25%)",
    ]);

    await i18n.changeLanguage("ko");
    try {
      view.rerender(<MemoryRouter><AccountsPage /></MemoryRouter>);
      const koPlans = within(screen.getByRole("region", { name: "플랜별 계정" }));
      expect(koPlans.getAllByRole("button")[0]).toHaveTextContent("알 수 없음3 (75%)");
    } finally {
      await i18n.changeLanguage("en");
    }
  });

  it("counts all account statuses and keeps unknown statuses separate from active", () => {
    mockAccountsData([
      "active", "paused", "rate_limited", "quota_exceeded", "reauth_required",
      "deactivated", "future_status", "active",
    ].map((status, index) => account({ accountId: `status-${index}`, status })));

    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    const statuses = within(screen.getByRole("region", { name: "Accounts by status" }));
    expect(statuses.getByTestId("donut-center-total")).toHaveTextContent(/^8$/);
    expect(statuses.getAllByRole("button").map((row) => row.textContent)).toEqual([
      "Active2 (25%)",
      "Paused1 (12.5%)",
      "Rate limited1 (12.5%)",
      "Quota exceeded1 (12.5%)",
      "Re-auth required1 (12.5%)",
      "Deactivated1 (12.5%)",
      "Unknown1 (12.5%)",
    ]);
  });

  it("keeps chart totals for the full inventory while filtering and switching views", async () => {
    const user = userEvent.setup();
    mockAccountsData([
      account({ accountId: "available", displayName: "Available account" }),
      account({ accountId: "disabled", status: "deactivated" }),
      account({ accountId: "expired", planType: "pro", status: "reauth_required" }),
    ]);
    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    const expectInventoryCounts = () => {
      const plans = within(screen.getByRole("region", { name: "Accounts by plan" }));
      const statuses = within(screen.getByRole("region", { name: "Accounts by status" }));
      expect(plans.getByTestId("donut-center-total")).toHaveTextContent(/^3$/);
      expect(statuses.getByTestId("donut-center-total")).toHaveTextContent(/^3$/);
      expect(plans.getAllByRole("button").map((row) => row.textContent)).toEqual([
        "Plus2 (66.7%)", "Pro1 (33.3%)",
      ]);
      expect(statuses.getAllByRole("button").map((row) => row.textContent)).toEqual([
        "Active1 (33.3%)", "Re-auth required1 (33.3%)", "Deactivated1 (33.3%)",
      ]);
    };

    await user.click(screen.getByRole("button", { name: "List view" }));
    await user.click(screen.getByRole("combobox", { name: "Filter accounts by plan" }));
    await user.click(screen.getByRole("option", { name: "Plus" }));
    expect(screen.getAllByTestId("account-list-overview-row")).toHaveLength(2);
    expectInventoryCounts();

    await user.click(screen.getByRole("combobox", { name: "Filter accounts by status" }));
    await user.click(screen.getByRole("option", { name: "Active" }));
    expect(screen.getAllByTestId("account-list-overview-row")).toHaveLength(1);
    expectInventoryCounts();

    await user.type(screen.getByPlaceholderText("Search accounts..."), "absent");
    expect(screen.getByText("No matching accounts")).toBeInTheDocument();
    expectInventoryCounts();

    for (const view of ["Grid view", "Detail view"]) {
      await user.click(screen.getByRole("button", { name: view }));
      expect(screen.getByText("No matching accounts")).toBeInTheDocument();
      expectInventoryCounts();
    }
  });

  it("keeps both distributions unchanged when paging through the account list", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("codex-lb-accounts-view-mode", "list");
    mockAccountsData(Array.from({ length: 25 }, (_, index) => account({
      accountId: `paged-${index}`,
      planType: index < 24 ? "plus" : "pro",
      status: index < 24 ? "active" : "deactivated",
    })));
    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    for (const rowCount of [24, 1]) {
      expect(screen.getAllByTestId("account-list-overview-row")).toHaveLength(rowCount);
      const plans = within(screen.getByRole("region", { name: "Accounts by plan" }));
      const statuses = within(screen.getByRole("region", { name: "Accounts by status" }));
      expect(plans.getByTestId("donut-center-total")).toHaveTextContent(/^25$/);
      expect(statuses.getByTestId("donut-center-total")).toHaveTextContent(/^25$/);
      expect(plans.getAllByRole("button").map((row) => row.textContent)).toEqual([
        "Plus24 (96%)", "Pro1 (4%)",
      ]);
      expect(statuses.getAllByRole("button").map((row) => row.textContent)).toEqual([
        "Active24 (96%)", "Deactivated1 (4%)",
      ]);
      if (rowCount === 24) {
        await user.click(screen.getByRole("button", { name: "Next" }));
      }
    }
  });

  it("updates both distributions when refreshed account data changes", () => {
    mockAccountsData([
      account({ accountId: "first" }),
      account({ accountId: "second", status: "deactivated" }),
    ]);
    const view = render(<MemoryRouter><AccountsPage /></MemoryRouter>);
    expect(screen.getAllByTestId("donut-center-total").map((total) => total.textContent)).toEqual(["2", "2"]);

    mockAccountsData(["plus", "pro", "pro"].map((planType, index) =>
      account({ accountId: `refreshed-${index}`, planType, status: "reauth_required" }),
    ));
    view.rerender(<MemoryRouter><AccountsPage /></MemoryRouter>);

    const plans = within(screen.getByRole("region", { name: "Accounts by plan" }));
    const statuses = within(screen.getByRole("region", { name: "Accounts by status" }));
    expect(plans.getByTestId("donut-center-total")).toHaveTextContent(/^3$/);
    expect(statuses.getByTestId("donut-center-total")).toHaveTextContent(/^3$/);
    expect(plans.getAllByRole("button").map((row) => row.textContent)).toEqual([
      "Pro2 (66.7%)", "Plus1 (33.3%)",
    ]);
    expect(statuses.getAllByRole("button").map((row) => row.textContent)).toEqual([
      "Re-auth required3 (100%)",
    ]);
  });

  it("shows zero totals and empty chart messages for an empty inventory", () => {
    mockAccountsData([]);
    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    for (const title of ["Accounts by plan", "Accounts by status"]) {
      const chart = within(screen.getByRole("region", { name: title }));
      expect(chart.getByTestId("donut-center-total")).toHaveTextContent(/^0$/);
      expect(chart.getByText("No data yet")).toBeInTheDocument();
      expect(chart.queryByRole("button")).not.toBeInTheDocument();
    }
  });

  it.each([
    ["loading", null],
    ["failed", new Error("Unable to load accounts")],
  ])("does not show empty charts while account loading is %s without data", (_state, error) => {
    mockAccountsData(undefined, error);
    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    expect(screen.queryByRole("region", { name: "Accounts by plan" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Accounts by status" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("donut-center-total")).not.toBeInTheDocument();
    if (error) {
      expect(screen.getByText(error.message)).toBeInTheDocument();
    }
  });

  it("shows a later action error over a failed background poll that kept its data", () => {
    mockAccountsData([account({ accountId: "polled" })], new Error("Background poll failed"), {
      importMutation: { ...idleMutation(), error: new Error("Import rejected") },
    });
    render(<MemoryRouter><AccountsPage /></MemoryRouter>);

    expect(screen.getByText("Import rejected")).toBeInTheDocument();
    expect(screen.queryByText("Background poll failed")).not.toBeInTheDocument();
  });

  it("defaults to the original inline detail layout and keeps overview modes optional", async () => {
    const user = userEvent.setup();
    mockedUseAccounts.mockReturnValue({
      accountsQuery: {
        data: [
          account({
            accountId: "acc-api-first",
            email: "api-first@example.com",
            displayName: "API First",
            resetAtSecondary: "2026-01-01T13:00:00.000Z",
            windowMinutesSecondary: 10_080,
          }),
          account({
            accountId: "acc-visible-first",
            email: "visible-first@example.com",
            displayName: "Visible First",
            resetAtSecondary: "2026-01-01T12:10:00.000Z",
            windowMinutesSecondary: 10_080,
          }),
        ],
        error: null,
        refetch: vi.fn(),
      },
      importMutation: idleMutation(),
      pauseMutation: idleMutation(),
      resumeMutation: idleMutation(),
      probeMutation: idleMutation(),
      usageResetMutation: idleMutation(),
      deleteMutation: idleMutation(),
      exportAuthMutation: idleMutation(),
      setAliasMutation: idleMutation(),
      limitWarmupMutation: idleMutation(),
      routingPolicyMutation: idleMutation(),
      subscriptionRefreshMutation: idleMutation(),
      subscriptionRefreshingAccountIds: [],
      updateMutation: idleMutation(),
    } as unknown as ReturnType<typeof useAccounts>);

    render(
      <MemoryRouter>
        <AccountsPage />
      </MemoryRouter>,
    );

    expect(
      screen
        .getAllByText(/^(Visible First|API First)$/)
        .map((el) => el.textContent),
    ).toEqual(["Visible First", "API First", "Visible First"]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Detail view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("accounts-inline-detail")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /API First/ }));
    expect(screen.getByRole("heading", { name: "API First" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "List view" }));
    expect(screen.queryByTestId("accounts-inline-detail")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View details for API First" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "API First" })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Detail view" }));
    expect(within(screen.getByTestId("accounts-inline-detail")).getByRole("heading", { name: "API First" })).toBeInTheDocument();
    expect(window.localStorage.getItem("codex-lb-accounts-view-mode")).toBe("detail");
  });

  it("renders account panels with mobile-first responsive containment", () => {
    mockedUseAccounts.mockReturnValue({
      accountsQuery: {
        data: [
          account({
            accountId: "acc-long",
            email: "very.long.account.identity.for.mobile@example-enterprise-workspace.invalid",
            displayName: "very.long.account.identity.for.mobile@example-enterprise-workspace.invalid",
          }),
        ],
        error: null,
        refetch: vi.fn(),
      },
      importMutation: idleMutation(),
      pauseMutation: idleMutation(),
      resumeMutation: idleMutation(),
      probeMutation: idleMutation(),
      usageResetMutation: idleMutation(),
      deleteMutation: idleMutation(),
      exportAuthMutation: idleMutation(),
      setAliasMutation: idleMutation(),
      limitWarmupMutation: idleMutation(),
      routingPolicyMutation: idleMutation(),
      subscriptionRefreshMutation: idleMutation(),
      subscriptionRefreshingAccountIds: [],
      updateMutation: idleMutation(),
    } as unknown as ReturnType<typeof useAccounts>);

    render(
      <MemoryRouter>
        <AccountsPage />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("accounts-layout")).toHaveClass(
      "grid-cols-1",
      "min-w-0",

    );
    expect(screen.getByTestId("accounts-list-panel")).toHaveClass(
      "min-w-0",
      "min-h-0",
      "self-start",
    );
    expect(screen.getByTestId("accounts-list-panel")).not.toHaveClass("h-full");
    expect(screen.getByTestId("accounts-list-card")).not.toHaveClass("h-full");
    expect(screen.getByTestId("accounts-inline-detail")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps helper instructions accessible when no accounts exist", async () => {
    const user = userEvent.setup();

    mockedUseAccounts.mockReturnValue({
      accountsQuery: {
        data: [],
        error: null,
        refetch: vi.fn(),
      },
      importMutation: idleMutation(),
      pauseMutation: idleMutation(),
      resumeMutation: idleMutation(),
      probeMutation: idleMutation(),
      usageResetMutation: idleMutation(),
      deleteMutation: idleMutation(),
      exportAuthMutation: idleMutation(),
      setAliasMutation: idleMutation(),
      limitWarmupMutation: idleMutation(),
      routingPolicyMutation: idleMutation(),
      subscriptionRefreshMutation: idleMutation(),
      subscriptionRefreshingAccountIds: [],
      updateMutation: idleMutation(),
    } as unknown as ReturnType<typeof useAccounts>);

    render(
      <MemoryRouter>
        <AccountsPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Need help?" }));
    expect(screen.getByText("Windows OAuth Help")).toBeInTheDocument();
  });

  it("confirms before resetting selected account usage", async () => {
    const user = userEvent.setup();
    const resetUsage = vi.fn().mockResolvedValue({
      status: "reset",
      accountId: "acc-reset",
      code: "reset",
      windowsReset: 2,
      usageWritten: true,
      primaryUsedPercentBefore: 100,
      primaryUsedPercentAfter: 2,
      secondaryUsedPercentBefore: 80,
      secondaryUsedPercentAfter: 0,
      accountStatusBefore: "rate_limited",
      accountStatusAfter: "active",
    });

    mockedUseAccounts.mockReturnValue({
      accountsQuery: {
        data: [
          account({
            accountId: "acc-reset",
            email: "reset@example.com",
            displayName: "Resettable",
            resetAtSecondary: "2026-01-01T13:00:00.000Z",
            windowMinutesSecondary: 10_080,
          }),
        ],
        error: null,
        refetch: vi.fn(),
      },
      importMutation: idleMutation(),
      pauseMutation: idleMutation(),
      resumeMutation: idleMutation(),
      probeMutation: idleMutation(),
      usageResetMutation: {
        isPending: false,
        error: null,
        mutateAsync: resetUsage,
      },
      deleteMutation: idleMutation(),
      exportAuthMutation: idleMutation(),
      setAliasMutation: idleMutation(),
      limitWarmupMutation: idleMutation(),
      routingPolicyMutation: idleMutation(),
      subscriptionRefreshMutation: idleMutation(),
      subscriptionRefreshingAccountIds: [],
      updateMutation: idleMutation(),
    } as unknown as ReturnType<typeof useAccounts>);

    render(
      <MemoryRouter>
        <AccountsPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /^Resettable/ }));
    await user.click(screen.getByRole("button", { name: "Reset usage" }));

    const dialog = await screen.findByRole("alertdialog", { name: "Reset usage" });
    expect(resetUsage).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole("button", { name: "Reset" }));

    await waitFor(() => {
      expect(resetUsage).toHaveBeenCalledWith({ accountId: "acc-reset" });
    });
  });

  it("opens a linked account and keeps force probe as an immediate action", async () => {
    const user = userEvent.setup();
    const probe = vi.fn().mockResolvedValue({
      status: "probed",
      accountId: "acc-probe",
      probeStatusCode: 200,
      primaryUsedPercentBefore: 10,
      primaryUsedPercentAfter: 9,
      secondaryUsedPercentBefore: 20,
      secondaryUsedPercentAfter: 19,
      accountStatusBefore: "active",
      accountStatusAfter: "active",
    });

    mockedUseAccounts.mockReturnValue({
      accountsQuery: {
        data: [
          account({
            accountId: "acc-probe",
            email: "probe@example.com",
            displayName: "Probe account",
            resetAtSecondary: "2026-01-01T13:00:00.000Z",
            windowMinutesSecondary: 10_080,
          }),
        ],
        error: null,
        refetch: vi.fn(),
      },
      importMutation: idleMutation(),
      pauseMutation: idleMutation(),
      resumeMutation: idleMutation(),
      probeMutation: {
        isPending: false,
        error: null,
        mutateAsync: probe,
      },
      usageResetMutation: idleMutation(),
      deleteMutation: idleMutation(),
      exportAuthMutation: idleMutation(),
      setAliasMutation: idleMutation(),
      limitWarmupMutation: idleMutation(),
      routingPolicyMutation: idleMutation(),
      subscriptionRefreshMutation: idleMutation(),
      subscriptionRefreshingAccountIds: [],
      updateMutation: idleMutation(),
    } as unknown as ReturnType<typeof useAccounts>);

    render(
      <MemoryRouter initialEntries={["/accounts?selected=acc-probe"]}>
        <AccountsPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Force probe" }));

    expect(probe).toHaveBeenCalledWith({ accountId: "acc-probe" });
    expect(screen.queryByRole("alertdialog", { name: "Reset usage" })).not.toBeInTheDocument();
  });
});
