import type { AccountSummary } from "@/features/accounts/schemas";

function isNewer(current: string | null | undefined, incoming: string | null | undefined): boolean {
  return current != null && (incoming == null || Date.parse(current) > Date.parse(incoming));
}

function sameAccountIdentity(current: AccountSummary, incoming: AccountSummary): boolean {
  const currentWorkspace = current.workspaceId || current.workspaceLabel || null;
  const incomingWorkspace = incoming.workspaceId || incoming.workspaceLabel || null;
  return current.accountId === incoming.accountId
    && current.planType === incoming.planType
    && (current.chatgptAccountId ?? null) === (incoming.chatgptAccountId ?? null)
    && current.email === incoming.email
    && (current.workspaceId ?? null) === (incoming.workspaceId ?? null)
    && currentWorkspace === incomingWorkspace;
}

/**
 * Apply an incoming account snapshot while retaining a newer compatible term.
 * The incoming snapshot remains authoritative for every field other than the
 * subscription, so reset quota/status updates are never lost.
 */
export function mergeAccountSnapshot(current: AccountSummary, incoming: AccountSummary): AccountSummary {
  if (!isNewer(current.subscription?.lastCheckedAt, incoming.subscription?.lastCheckedAt)) return incoming;
  return mergeSubscriptionRefresh(incoming, current);
}

export function mergeSubscriptionRefresh(current: AccountSummary, incoming: AccountSummary): AccountSummary {
  if (
    !sameAccountIdentity(current, incoming) ||
    isNewer(current.lastRefreshAt, incoming.lastRefreshAt) ||
    isNewer(current.subscription?.lastCheckedAt, incoming.subscription?.lastCheckedAt)
  ) {
    return current;
  }
  return { ...current, subscription: incoming.subscription };
}
