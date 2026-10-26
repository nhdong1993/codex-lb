import { Users } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { AlertMessage } from "@/components/alert-message";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { AccountsViewTabs } from "@/features/accounts/components/accounts-view-tabs";
import { useAccounts } from "@/features/accounts/hooks/use-accounts";
import {
  OVERVIEW_STATUS_ORDER,
  QUOTA_BIN_COUNT,
  summarizeAccountsByPlan,
  type PlanOverview,
  type WindowOverview,
} from "@/features/accounts/overview";
import { cn } from "@/lib/utils";
import { quotaBarColor, type DashboardAccountStatus } from "@/utils/account-status";
import { getErrorMessageOrNull } from "@/utils/errors";
import { formatPercentNullable, formatQuotaResetLabel, formatSlug } from "@/utils/formatters";

// Same hues as StatusBadge, as solid fills for the stacked bar and legend dots.
const STATUS_FILL: Record<DashboardAccountStatus, string> = {
  active: "bg-emerald-500",
  paused: "bg-amber-500",
  limited: "bg-orange-500",
  exceeded: "bg-red-500",
  reauth: "bg-sky-500",
  deactivated: "bg-zinc-400",
};

export function AccountsOverviewPage() {
  const { t } = useTranslation();
  const { accountsQuery } = useAccounts();
  // Not memoized on `data`: a poll that returns identical data keeps the same reference,
  // and the next reset must still move past resets that have elapsed since.
  const rows = summarizeAccountsByPlan(accountsQuery.data ?? []);
  const error = getErrorMessageOrNull(accountsQuery.error);

  return (
    <div className="animate-fade-in-up space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("accounts.overview.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("accounts.overview.subtitle")}</p>
        </div>
        <AccountsViewTabs />
      </div>

      {error ? (
        <div role="alert">
          <AlertMessage variant="error">{error}</AlertMessage>
        </div>
      ) : null}

      {!accountsQuery.data ? (
        error ? null : (
          <div data-testid="accounts-overview-loading" className="space-y-6">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-44 w-full rounded-xl" />
            ))}
          </div>
        )
      ) : rows.length === 0 ? (
        <EmptyState icon={Users} title={t("accounts.list.emptyTitle")} description={t("accounts.list.emptyDescription")} />
      ) : (
        rows.map((row) => <PlanSection key={row.plan ?? ""} row={row} />)
      )}
    </div>
  );
}

function PlanSection({ row }: { row: PlanOverview }) {
  const { t } = useTranslation();
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <h2 id={headingId} className="text-sm font-semibold">
        {row.plan === null ? t("accounts.overview.allPlans") : formatSlug(row.plan)}
        <span className="font-normal text-muted-foreground"> · {t("accounts.overview.accountCount", { count: row.total })}</span>
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatusTile row={row} />
        {row.windows.map((window) => (
          <QuotaTile key={window.key} window={window} total={row.total} />
        ))}
      </div>
    </section>
  );
}

function StatusTile({ row }: { row: PlanOverview }) {
  const { t } = useTranslation();
  const present = OVERVIEW_STATUS_ORDER.filter((status) => row.statusCounts[status] > 0);

  return (
    <div className="min-w-0 rounded-xl border bg-card p-4">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{t("accounts.overview.status")}</p>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tabular-nums">{row.statusCounts.active}</span>
        <span className="text-xs text-muted-foreground">{t("accounts.overview.activeOf", { total: row.total })}</span>
      </p>
      {/* The legend below carries the same counts as text. */}
      <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        {present.map((status) => (
          <span
            key={status}
            className={STATUS_FILL[status]}
            style={{ width: `${(row.statusCounts[status] / row.total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {present.map((status) => (
          <li key={status} className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full", STATUS_FILL[status])} aria-hidden="true" />
            <span className="text-muted-foreground">{t(`common.status.${status}`)}</span>
            <span className="font-semibold tabular-nums">{row.statusCounts[status]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function QuotaTile({ window, total }: { window: WindowOverview; total: number }) {
  const { t } = useTranslation();
  const bucketsId = useId();
  const label = window.key === "primary" ? "5h" : t(window.key === "secondary" ? "common.quota.weekly" : "common.quota.monthly");
  const average = formatPercentNullable(window.avgRemaining);
  const tallest = Math.max(...window.bins);
  const summary =
    window.avgRemaining === null
      ? t("accounts.overview.histogramNoData", { window: label })
      : t("accounts.overview.histogramSummary", { window: label, average, known: window.known, total });
  const buckets = window.bins.map((count, index) => {
    const from = index * 10;
    return { from, count, title: t("accounts.overview.binTitle", { from, to: index === QUOTA_BIN_COUNT - 1 ? 100 : from + 10, count }) };
  });

  return (
    <div className="min-w-0 rounded-xl border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="text-[11px] tabular-nums text-muted-foreground">
          {t("accounts.overview.withData", { known: window.known, total })}
        </p>
      </div>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span
          className={cn(
            "text-2xl font-semibold tabular-nums",
            window.avgRemaining === null
              ? "text-muted-foreground"
              : window.avgRemaining >= 70
                ? "text-emerald-600 dark:text-emerald-400"
                : window.avgRemaining >= 30
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-red-600 dark:text-red-400",
          )}
        >
          {window.avgRemaining === null ? "–" : average}
        </span>
        <span className="text-xs text-muted-foreground">
          {window.avgRemaining === null ? t("accounts.overview.noData") : t("accounts.overview.avgRemaining")}
        </span>
      </p>
      <div role="img" aria-label={summary} aria-describedby={bucketsId} className="mt-3 flex h-14 items-end gap-0.5">
        {buckets.map(({ from, count, title }) => (
          <div key={from} title={title} className="flex h-full flex-1 items-end rounded-sm bg-muted/50">
            <div
              className={cn("w-full rounded-sm", quotaBarColor(from + 5))}
              // Each tile scales to its own tallest bucket; max(1, …) keeps an empty window at zero height.
              style={{ height: `${(count / Math.max(1, tallest)) * 100}%` }}
            />
          </div>
        ))}
      </div>
      <p id={bucketsId} className="sr-only">
        {buckets.map((bucket) => bucket.title).join(", ")}
      </p>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-muted-foreground">
        <span>0%</span>
        {tallest > 0 ? <span>{t("accounts.overview.tallest", { count: tallest })}</span> : null}
        <span>100%</span>
      </div>
      <p className="mt-2 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
        <span className={cn(window.lowCount > 0 && "font-medium text-red-600 dark:text-red-400")}>
          {t("accounts.overview.lowCount", { count: window.lowCount })}
        </span>
        {window.nextResetAt ? (
          <span>{t("accounts.overview.nextReset", { label: formatQuotaResetLabel(window.nextResetAt) })}</span>
        ) : null}
      </p>
    </div>
  );
}
