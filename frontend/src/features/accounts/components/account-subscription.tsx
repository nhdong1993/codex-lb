import { RefreshCw } from "lucide-react";
import {
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { AccountClock, useAccountClock } from "@/features/accounts/hooks/use-account-clock";
import type { AccountSummary } from "@/features/accounts/schemas";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { cn } from "@/lib/utils";
import { formatDateTimeInline } from "@/utils/formatters";

export function AccountClockProvider({ children }: { children: ReactNode }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return <AccountClock.Provider value={now}>{children}</AccountClock.Provider>;
}

export function AccountSubscription({
  account,
  compact = false,
  onRefresh,
  refreshing = false,
  refreshDisabled = false,
}: {
  account: AccountSummary;
  compact?: boolean;
  onRefresh?: (accountId: string) => void;
  refreshing?: boolean;
  refreshDisabled?: boolean;
}) {
  const { t } = useTranslation();
  const now = useAccountClock();
  const dateFormat = useDateDisplayFormatStore((s) => s.dateDisplayFormat);
  const verifying = account.planCheckPending === true;
  const paid = !["free", "unknown"].includes(account.planType.toLowerCase());
  const end = paid && !verifying ? account.subscription?.activeUntil : null;
  const endMs = end ? Date.parse(end) : NaN;
  const known = Number.isFinite(endMs);
  const remaining = endMs - now;
  const checked = account.subscription?.lastCheckedAt;
  const duration = `${Math.floor(Math.max(0, remaining) / 86_400_000)}d ${Math.floor(Math.max(0, remaining) / 3_600_000) % 24}h`;
  const source = account.subscription?.source;
  const sourceLabel = source
    ? t(source === "subscriptions_api"
        ? "accounts.subscription.apiSource"
        : "accounts.subscription.tokenSource")
    : null;
  const summary = verifying
    ? t("accounts.subscription.verifying")
    : !known
      ? t("accounts.subscription.unknown")
      : remaining <= 0
        ? t("accounts.subscription.elapsed")
        : t("accounts.subscription.remaining", { duration });
  const hint = verifying
    ? "accounts.subscription.verifyingHint"
    : known
      ? "accounts.subscription.recordedHint"
      : "accounts.subscription.unknownHint";
  const refreshButton = onRefresh ? (
    <Button
      type="button"
      variant="ghost"
      size="icon-xs"
      className="pointer-events-auto relative z-10 ml-1"
      aria-label={t("accounts.subscription.refreshFor", { account: account.displayName || account.email })}
      title={t("accounts.subscription.refresh")}
      disabled={refreshDisabled || refreshing || ["free", "unknown"].includes(account.planType.toLowerCase()) || ["deactivated", "reauth_required"].includes(account.status)}
      onClick={(event) => {
        event.stopPropagation();
        onRefresh(account.accountId);
      }}
    >
      <RefreshCw className={cn("size-3", refreshing && "animate-spin")} aria-hidden="true" />
    </Button>
  ) : null;

  if (compact) {
    const description = [
      `${t("accounts.subscription.title")}: ${summary}`,
      sourceLabel ? `${t("accounts.subscription.source")}: ${sourceLabel}` : null,
      known
        ? `${t("accounts.subscription.until")}: ${formatDateTimeInline(end, dateFormat)}`
        : null,
      checked
        ? `${t("accounts.subscription.checked")}: ${formatDateTimeInline(checked, dateFormat)}`
        : null,
      t(hint),
    ]
      .filter(Boolean)
      .join("\n");
    return (
      <>
        <span
          data-testid="account-plan-remaining"
          className={cn(
            "pointer-events-auto whitespace-nowrap text-[11px] font-medium tabular-nums",
            known &&
              remaining <= 3 * 86_400_000 &&
              "text-amber-600 dark:text-amber-400",
          )}
          title={description}
          aria-label={description}
        >
          {verifying
            ? t("accounts.subscription.verifying")
            : !known
            ? t("accounts.subscription.unknown")
            : remaining <= 0
              ? t("accounts.subscription.elapsedShort")
              : duration}
        </span>
        {refreshButton}
      </>
    );
  }

  return (
    <section
      className="min-w-0 space-y-2 rounded-lg border bg-muted/30 p-4"
      aria-label={t("accounts.subscription.title")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-muted-foreground">
          {t("accounts.subscription.title")}
        </h3>
        <div className="flex items-center gap-1">
          <span
            className={cn(
              "text-sm font-semibold tabular-nums",
              known &&
                remaining <= 3 * 86_400_000 &&
                "text-amber-600 dark:text-amber-400",
            )}
          >
            {summary}
          </span>
          {refreshButton}
        </div>
      </div>
      <dl className="space-y-1 text-xs text-muted-foreground">
        {sourceLabel ? (
          <div className="flex flex-wrap justify-between gap-x-2">
            <dt>{t("accounts.subscription.source")}</dt>
            <dd>{sourceLabel}</dd>
          </div>
        ) : null}
        {known ? (
          <div className="flex flex-wrap justify-between gap-x-2">
            <dt>{t("accounts.subscription.until")}</dt>
            <dd>{formatDateTimeInline(end, dateFormat)}</dd>
          </div>
        ) : null}
        {checked ? (
          <div className="flex flex-wrap justify-between gap-x-2">
            <dt>{t("accounts.subscription.checked")}</dt>
            <dd>{formatDateTimeInline(checked, dateFormat)}</dd>
          </div>
        ) : null}
      </dl>
      <p className="text-[11px] text-muted-foreground">
        {t(hint)}
      </p>
    </section>
  );
}
