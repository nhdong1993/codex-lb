# Proposal

## Why

An account reset reconciliation can finish after a successful subscription refresh and publish an older account snapshot over the newer recorded plan term. This makes the dashboard briefly, and sometimes persistently, show a stale subscription deadline even though the refresh succeeded.

## What Changes

- Preserve the newest compatible subscription term when reset-quota summaries are merged.
- Keep the list cache, dashboard cache, and reset reconciliation state aligned after either operation completes.
- Add a regression test for a delayed reset summary arriving after a successful subscription refresh.

## Capabilities

### New Capabilities

### Modified Capabilities

- `account-subscription-term`: subscription refresh results remain authoritative over older compatible reset-summary snapshots while quota reconciliation still updates usage data.

## Impact

- Frontend account and dashboard query reconciliation and its tests.
- No API or persistence schema changes.
