# Design

## Context

The accounts list and dashboard use targeted reset summaries as optimistic reconciliation inputs while periodic account queries continue to run. A reset summary is authoritative for quota and status fields, but it can contain subscription data captured before a manual subscription refresh. The current reconciliation state also feeds later polling responses, so correcting only the visible query cache would leave a second overwrite path.

## Goals / Non-Goals

**Goals:**

- Merge reset summaries with the newest compatible subscription term already held by the client.
- Publish the same merged account to list and dashboard caches and retain it in reset reconciliation state.
- Prevent polls started before a merge from restoring the previous term; fresh polls remain authoritative for account identity and subscription.
- Cover the overlap through the public `useAccounts` mutation/query path.

**Non-Goals:**

- Change the subscription API, backend persistence, refresh schedule, or reset-credit API.
- Reconcile unrelated account identity or plan changes across snapshots.
- Change quota aggregation rules beyond applying the reset summary as today.

## Decisions

1. **Use one compatibility-aware account merge helper.** A snapshot may donate only its subscription when account ID, plan, ChatGPT account, email and workspace match. The incoming reset snapshot remains the base object so its quota, status and usage fields win; a newer compatible subscription is copied over it. This avoids duplicating timestamp and identity rules in each cache update.

2. **Store the merged snapshot in reconciliation state.** Reset merges store their effective snapshot. When a manual subscription refresh updates existing reset state, it changes only the subscription and advances the state generation. Polls that started before the merge therefore return the stored merged snapshot. Subscription refreshes do not create reset state, and later fresh polls stay authoritative. In-flight list and dashboard reads are cancelled before publishing a manual refresh.

3. **Keep the projections aligned.** Reset summaries collect newer compatible subscriptions from existing reset state and all list/dashboard caches, then publish the same effective summary. Manual subscription refreshes apply their source guard independently to each cache and only replace subscription fields. Dashboard quota aggregates continue to be recomputed only for reset summaries; subscription-only updates do not disturb those aggregates.

4. **Prefer explicit newer check timestamps.** A current subscription with a later `lastCheckedAt` (including a checked result when the incoming snapshot has no check time) is retained only when the existing manual-refresh source and credential timestamp guards also pass. Equal timestamps keep the incoming snapshot. An incoming explicit newer inactive result remains authoritative, and identity or plan mismatches never transplant a term.

## Risks / Trade-offs

- **[Risk]** A client may retain a term until a compatible authoritative snapshot arrives. → **Mitigation:** only retain it for matching identity/plan/workspace and compare recorded check timestamps; newer explicit inactive results replace it.
- **[Risk]** More state transitions could make a stale query appear successful. → **Mitigation:** keep the existing generation check and add a regression test that waits for the delayed reset response before asserting both quota and subscription.

## Migration Plan

No migration is required. The change is frontend-only and takes effect on the next dashboard load.
