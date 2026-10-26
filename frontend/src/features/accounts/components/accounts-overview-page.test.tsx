import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountsOverviewPage } from "@/features/accounts/components/accounts-overview-page";
import { useAccounts } from "@/features/accounts/hooks/use-accounts";
import type { AccountSummary } from "@/features/accounts/schemas";
import { createAccountSummary } from "@/test/mocks/factories";

vi.mock("@/features/accounts/hooks/use-accounts", () => ({
  useAccounts: vi.fn(),
}));

function mockAccounts(data: AccountSummary[] | undefined, error: Error | null = null) {
  vi.mocked(useAccounts).mockReturnValue({
    accountsQuery: { data, error },
  } as unknown as ReturnType<typeof useAccounts>);
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/accounts/overview"]}>
      <AccountsOverviewPage />
    </MemoryRouter>,
  );
}

const plusActive = createAccountSummary({
  accountId: "plus_1",
  planType: "plus",
  status: "active",
  usage: { primaryRemainingPercent: 100, secondaryRemainingPercent: null, monthlyRemainingPercent: null },
});
const plusLimited = createAccountSummary({
  accountId: "plus_2",
  planType: "plus",
  status: "rate_limited",
  usage: { primaryRemainingPercent: 9.9, secondaryRemainingPercent: null, monthlyRemainingPercent: null },
});
const freeMonthly = createAccountSummary({
  accountId: "free_1",
  planType: "free",
  status: "active",
  usage: { primaryRemainingPercent: null, secondaryRemainingPercent: null, monthlyRemainingPercent: 40 },
  windowMinutesPrimary: null,
  windowMinutesSecondary: null,
  windowMinutesMonthly: 43_200,
  resetAtPrimary: null,
  resetAtSecondary: null,
});

describe("AccountsOverviewPage", () => {
  beforeEach(() => {
    vi.mocked(useAccounts).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the all-plans row first, then one row per plan with status counts", () => {
    mockAccounts([freeMonthly, plusActive, plusLimited]);
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "Accounts overview" })).toBeInTheDocument();
    const regions = screen.getAllByRole("region");
    expect(regions).toHaveLength(3);
    expect(within(regions[0]).getByRole("heading", { level: 2 })).toHaveTextContent("All plans");
    expect(within(regions[1]).getByRole("heading", { level: 2 })).toHaveTextContent("Plus");
    expect(within(regions[2]).getByRole("heading", { level: 2 })).toHaveTextContent("Free");

    const plus = regions[1];
    expect(within(plus).getByText("of 2 active")).toBeInTheDocument();
    expect(within(plus).getByText("Rate limited")).toBeInTheDocument();
  });

  it("summarizes each quota histogram in text, skipping missing values", () => {
    mockAccounts([plusActive, plusLimited]);
    renderPage();

    const plus = screen.getByRole("region", { name: /Plus/ });
    expect(
      within(plus).getByRole("img", { name: "5h: 55% average remaining across 2 of 2 accounts with data" }),
    ).toBeInTheDocument();
    expect(within(plus).getByText("1 below 10%")).toBeInTheDocument();
  });

  it("shows a dash instead of 0% for a window without data", () => {
    mockAccounts([plusActive, plusLimited]);
    renderPage();

    const plus = screen.getByRole("region", { name: /Plus/ });
    expect(within(plus).getByRole("img", { name: "Weekly: no data" })).toBeInTheDocument();
    expect(within(plus).getByText("0/2 with data")).toBeInTheDocument();
    expect(within(plus).getByText("–")).toBeInTheDocument();
  });

  it("lists every histogram bucket count in the accessible description", () => {
    mockAccounts([plusActive, plusLimited]);
    renderPage();

    const plus = screen.getByRole("region", { name: /Plus/ });
    const histogram = within(plus).getByRole("img", { name: /^5h:/ });
    expect(histogram).toHaveAccessibleDescription(/0–10% remaining: 1, 10–20% remaining: 0/);
    expect(histogram).toHaveAccessibleDescription(/90–100% remaining: 1$/);
  });

  it("moves the next reset past elapsed resets when a poll returns the same data", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-26T00:00:00Z"));
    // One array reference for both renders, as React Query keeps for an unchanged poll.
    const accounts = [
      createAccountSummary({ accountId: "a", resetAtPrimary: "2026-10-26T01:00:00Z", resetAtSecondary: null }),
      createAccountSummary({ accountId: "b", resetAtPrimary: "2026-10-26T03:00:00Z", resetAtSecondary: null }),
    ];
    mockAccounts(accounts);
    const view = renderPage();
    expect(within(screen.getByRole("region", { name: /Plus/ })).getByText("next reset in 1h")).toBeInTheDocument();

    vi.setSystemTime(new Date("2026-10-26T01:30:00Z"));
    view.rerender(
      <MemoryRouter initialEntries={["/accounts/overview"]}>
        <AccountsOverviewPage />
      </MemoryRouter>,
    );

    expect(within(screen.getByRole("region", { name: /Plus/ })).getByText("next reset in 1h 30m")).toBeInTheDocument();
  });

  it("gives a monthly-only plan a monthly tile and no 5-hour tile", () => {
    mockAccounts([freeMonthly, plusActive]);
    renderPage();

    const free = screen.getByRole("region", { name: /Free/ });
    expect(within(free).getByRole("img", { name: /^Monthly: 40% average/ })).toBeInTheDocument();
    expect(within(free).queryByRole("img", { name: /^5h:/ })).not.toBeInTheDocument();
  });

  it("marks only the Overview tab as current", () => {
    mockAccounts([plusActive]);
    renderPage();

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "List" })).not.toHaveAttribute("aria-current");
  });

  it("shows loading, error, and empty states", () => {
    mockAccounts(undefined);
    const { unmount } = renderPage();
    expect(screen.getByTestId("accounts-overview-loading")).toBeInTheDocument();
    unmount();

    mockAccounts(undefined, new Error("Accounts unavailable"));
    const errorView = renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent("Accounts unavailable");
    errorView.unmount();

    mockAccounts([]);
    renderPage();
    expect(screen.getByText("No accounts yet")).toBeInTheDocument();
  });
});
