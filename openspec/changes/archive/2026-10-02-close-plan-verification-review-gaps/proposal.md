## Why

Follow-up review reproduced three remaining failures: an in-flight paid check can swallow a newer Free observation, a WebSocket can close during its final model query, and HTTP bridge reuse bypasses shared model exclusion.

## What Changes

- Fence older verification results when another refresh records new Free evidence, preserving the original deadline and attempt budget.
- Check transport retirement after asynchronous model admission and transfer unsent WebSocket turns safely.
- Apply model exclusion to HTTP bridge reuse and dispatch while preserving hard ownership, accepted siblings and reservation cleanup.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usage-refresh-policy`: new evidence during in-flight verification.
- `account-routing`: model admission across reused transports and asynchronous dispatch checks.

## Impact

Priority-check repository and updater, direct WebSocket dispatch, HTTP bridge admission, and product-path regression tests. No new setting, schema or UI change.
