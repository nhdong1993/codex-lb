import { ArrowUpRight, Flame, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { isEmailLabel } from "@/components/blur-email";
import { MiniQuotaBar } from "@/components/mini-quota-bar";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AccountSubscription } from "@/features/accounts/components/account-subscription";
import { ACCOUNT_LIST_COLUMNS, ACCOUNT_LIST_COLUMNS_WITHOUT_RESET } from "@/features/accounts/components/account-list-layout";
import { useAccountClock } from "@/features/accounts/hooks/use-account-clock";
import type { AccountRoutingPolicy, AccountSummary } from "@/features/accounts/schemas";
import { usePrivacyStore } from "@/hooks/use-privacy";
import { useAccountQuotaDisplayStore } from "@/hooks/use-account-quota-display";
import { useSmoothPercent } from "@/hooks/use-smooth-percent";
import { cn } from "@/lib/utils";
import { planBadgeClass } from "@/utils/plan-badge";
import { normalizeStatus } from "@/utils/account-status";
import { formatCompactAccountId } from "@/utils/account-identifiers";
import {
  formatPercentNullable,
  formatQuotaResetLabel,
  formatSlug,
} from "@/utils/formatters";

type AccountListOverviewRowProps = {
  account: AccountSummary;
  selected: boolean;
  showAccountId?: boolean;
  showResetCreditBadge?: boolean;
  onRoutingPolicyChange?: (accountId: string, routingPolicy: AccountRoutingPolicy) => void;
  routingPolicyBusy?: boolean;
  readOnly?: boolean;
  onSubscriptionRefresh?: (accountId: string) => void;
  subscriptionRefreshing?: boolean;
  onSelect: (accountId: string) => void;
};

/** Compact overview with full metadata and management available in Detail view. */
export function AccountListOverviewRow({
  account,
  selected,
  showAccountId = false,
  showResetCreditBadge = true,
  onRoutingPolicyChange,
  routingPolicyBusy = false,
  readOnly = false,
  onSubscriptionRefresh,
  subscriptionRefreshing = false,
  onSelect,
}: AccountListOverviewRowProps) {
  const { t } = useTranslation();
  const now = useAccountClock();
  const resetCreditRemaining = Date.parse(account.resetCreditNearestExpiresAt ?? "") - now;
  const resetCreditExpiresSoon =
    (account.availableResetCredits ?? 0) > 0 &&
    resetCreditRemaining > 0 &&
    resetCreditRemaining <= 3 * 86_400_000;
  const blurred = usePrivacyStore((s) => s.blurred);
  const quotaDisplay = useAccountQuotaDisplayStore((s) => s.quotaDisplay);
  const status = normalizeStatus(account.status);
  const primary = useSmoothPercent(
    account.usage?.primaryRemainingPercent ?? null,
  );
  const secondary = useSmoothPercent(
    account.usage?.secondaryRemainingPercent ?? null,
  );
  const monthly = useSmoothPercent(
    account.usage?.monthlyRemainingPercent ?? null,
  );
  const hasPrimary =
    account.windowMinutesPrimary != null ||
    primary.everKnown ||
    account.resetAtPrimary != null;
  const hasSecondary =
    account.windowMinutesSecondary != null ||
    secondary.everKnown ||
    account.resetAtSecondary != null;
  const hasMonthly =
    account.windowMinutesMonthly != null ||
    monthly.everKnown ||
    account.resetAtMonthly != null;
  const monthlyOnly = hasMonthly && !hasPrimary && !hasSecondary;
  const showPrimary =
    !monthlyOnly && hasPrimary && (quotaDisplay !== "weekly" || !hasSecondary);
  const showSecondary =
    !monthlyOnly && hasSecondary && (quotaDisplay !== "5h" || !hasPrimary);
  const label = account.alias?.trim() || account.displayName || account.email;
  const workspace =
    account.workspaceLabel ||
    account.workspaceId ||
    account.chatgptAccountId ||
    t("accounts.detail.unknownWorkspace");

  return (
    <div
      role="group"
      data-testid="account-list-overview-row"
      className={cn(
        "group relative grid w-full min-w-0 grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-1.5 rounded-lg border bg-card px-4 py-2 text-left transition-colors hover:border-primary/30 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:py-2.5",
        showResetCreditBadge ? ACCOUNT_LIST_COLUMNS : ACCOUNT_LIST_COLUMNS_WITHOUT_RESET,
        selected && "border-primary/30 bg-primary/[0.03]",
      )}
    >
      <button
        type="button"
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-haspopup="dialog"
        aria-label={t("accounts.listOverview.detailsFor", { account: label })}
        onClick={() => onSelect(account.accountId)}
      />
      <div className="pointer-events-none relative col-span-3 min-w-0 lg:col-span-1">
        <div className="flex min-w-0 items-center gap-2">
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "truncate text-sm font-semibold",
                blurred &&
                  !account.alias &&
                  isEmailLabel(label, account.email) &&
                  "privacy-blur",
              )}
            >
              {label}
            </p>
          </div>
          {account.securityWorkAuthorized ? (
            <ShieldCheck
              className="size-4 shrink-0 text-emerald-600"
              aria-label={t("accounts.actions.trustedAccess")}
            />
          ) : null}
          {onRoutingPolicyChange ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className={cn(
                "pointer-events-auto relative z-10 size-7 shrink-0 p-0",
                account.routingPolicy === "burn_first" &&
                  "border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300 dark:hover:bg-amber-500/20",
              )}
              title={t("common.routingPolicies.burnFirst")}
              aria-pressed={account.routingPolicy === "burn_first"}
              aria-label={t("accounts.listOverview.toggleBurnFirst", { account: label })}
              disabled={readOnly || routingPolicyBusy || status === "reauth" || status === "deactivated"}
              onClick={(event) => {
                event.stopPropagation();
                onRoutingPolicyChange(
                  account.accountId,
                  account.routingPolicy === "burn_first" ? "normal" : "burn_first",
                );
              }}
            >
              <Flame className="size-3" aria-hidden="true" />
            </Button>
          ) : null}
          <ArrowUpRight
            className="size-3.5 shrink-0 text-muted-foreground group-hover:text-primary"
            aria-label={t("accounts.grid.details")}
          />
        </div>
        <p
          className="mt-1 truncate text-[11px] text-muted-foreground"
          title={
            showAccountId
              ? t("accounts.detail.accountIdTitle", {
                  accountId: account.accountId,
                })
              : workspace
          }
        >
          {label !== account.email ? (
            <>
              <span className={blurred ? "privacy-blur" : undefined}>
                {account.email}
              </span>
              {" · "}
            </>
          ) : null}
          <span>
            {workspace}
            {account.seatType ? ` · ${formatSlug(account.seatType)}` : ""}
          </span>
          {showAccountId
            ? ` | ID ${formatCompactAccountId(account.accountId)}`
            : ""}
        </p>
      </div>

      <div className="pointer-events-none col-span-3 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5 lg:contents">
        <div className="pointer-events-none relative min-w-0 shrink-0" data-testid="account-list-plan-cell">
          <Badge variant="outline" className={cn("text-[10px]", planBadgeClass(account.planType))}>
            {formatSlug(account.planType)}
          </Badge>
        </div>

        <div className="pointer-events-none relative min-w-0 shrink-0" data-testid="account-list-status-cell">
          <StatusBadge
            status={status}
            title={
              account.deactivationReason ||
              (status === "active"
                ? t("accounts.listItem.statusActiveHint")
                : undefined)
            }
          />
        </div>

        {showResetCreditBadge ? (
          <div className="pointer-events-none relative min-w-0 shrink-0" data-testid="account-list-reset-cell">
            {account.availableResetCredits != null ? (
              <span className="relative inline-flex">
                <Badge
                  variant="outline"
                  className="border-primary/20 bg-primary/5 text-[10px] tabular-nums text-primary"
                  title={t("accounts.resetCreditDialog.availableCount", {
                    count: account.availableResetCredits ?? 0,
                  })}
                >
                  {t("accounts.actions.resetWithCount", {
                    count: account.availableResetCredits ?? 0,
                  })}
                </Badge>
                {resetCreditExpiresSoon ? (
                  <span
                    role="img"
                    aria-label={t("accounts.listOverview.resetExpiringSoon")}
                    className="absolute -top-1.5 left-1/2 size-2 -translate-x-1/2 rounded-full bg-red-500 ring-2 ring-card"
                    data-testid="account-list-reset-expiry-dot"
                  />
                ) : null}
              </span>
            ) : <span className="text-xs text-muted-foreground">—</span>}
          </div>
        ) : null}
      </div>

      <div className="pointer-events-none relative col-span-3 min-w-0 lg:col-span-1">
        <span className="mr-1 text-[10px] text-muted-foreground lg:hidden">
          {t("accounts.listOverview.subscription")}
        </span>
        <AccountSubscription account={account} compact onRefresh={onSubscriptionRefresh} refreshing={subscriptionRefreshing} refreshDisabled={readOnly} />
      </div>

      <div
        className={cn(
          "pointer-events-none relative col-span-3 grid min-w-0 gap-4 lg:col-span-1",
          showPrimary && showSecondary ? "grid-cols-2" : "grid-cols-1",
        )}
      >
        {monthlyOnly ? (
          <QuotaCell
            label={t("common.quota.monthly")}
            percent={monthly.percent}
            resetAt={account.resetAtMonthly}
          />
        ) : null}
        {showPrimary ? (
          <QuotaCell
            label="5h"
            percent={primary.percent}
            resetAt={account.resetAtPrimary}
          />
        ) : null}
        {showSecondary ? (
          <QuotaCell
            label={t("common.quota.weekly")}
            percent={secondary.percent}
            resetAt={account.resetAtSecondary}
          />
        ) : null}
        {!monthlyOnly && !showPrimary && !showSecondary ? (
          <p className="text-xs text-muted-foreground">—</p>
        ) : null}
      </div>
    </div>
  );
}

function QuotaCell({
  label,
  percent,
  resetAt,
}: {
  label: string;
  percent: number | null;
  resetAt: string | null | undefined;
}) {
  const { t } = useTranslation();
  const reset = formatQuotaResetLabel(resetAt ?? null);
  return (
    <div className="min-w-0 space-y-1">
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="min-w-0 truncate" title={label}>
          {label}
        </span>
        <span className="shrink-0 font-medium tabular-nums">
          {formatPercentNullable(percent, 1)}
        </span>
      </div>
      <MiniQuotaBar
        aria-label={t("accounts.listItem.quotaRemainingAria", { label })}
        percent={percent}
        testId={`list-overview-quota-${label}`}
      />
      <p className="truncate text-[10px] text-muted-foreground" title={reset}>
        {reset.startsWith("Reset ")
          ? reset
          : t("accounts.listItem.resetAt", { label: reset })}
      </p>
    </div>
  );
}
