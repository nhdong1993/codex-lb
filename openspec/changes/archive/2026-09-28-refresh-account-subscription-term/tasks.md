## 1. Subscription source
- [x] 1.1 Add validated subscriptions client with curl_cffi and explicit route handling.
- [x] 1.2 Add nullable snapshot columns, migration and guarded persistence.
- [x] 1.3 Add bounded leader-owned refresh and lifespan cleanup; prefer snapshots in account summaries.

## 2. Display
- [x] 2.1 Render unpadded xd xh across views and label source/last check.

## 3. Verification
- [x] 3.1 Verify client errors, refresh races/cancellation, dashboard API and migration round-trip.
- [x] 3.2 Run frontend tests/typecheck/build and capture the updated display.
- [x] 3.3 Sync specs/context, run strict validation, verify and archive the change.
