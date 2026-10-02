## Context

See the reviewed `confirm-plan-downgrades-promptly` change. Guarded INSERT SELECT statements still read PostgreSQL MVCC snapshots before waiting on conflicting inserts, so an EXISTS condition alone cannot fence credential replacement.

## Decisions

- Lock the account row before priority enqueue and priority observation writes. On PostgreSQL use the same FOR NO KEY UPDATE mode as credential replacement, followed by fresh generation/credential checks in the held transaction. SQLite retains its writer section. Keep account-before-child lock ordering; no network work holds this lock.
- A first Free observation can reopen completed work only while attempts remain. Preserve requested_at and attempts, set a new generation and a 15-second due time. Repeated model errors remain coalesced and do not extend the exclusion window.
- Before a reused WebSocket sends response.create, consult model exclusion for its account and requested model. Reuse the existing unavailable-socket retirement and sibling rejection path. Movable work reselects; hard ownership fails closed; accepted siblings keep their socket.
- Add an opt-in settlement wait to OAuth singleflight for priority callers. If cancelled, wait for the shared exchange and guarded persistence to finish, then propagate cancellation. Do not cancel an exchange that may already have consumed a refresh token or that other callers share. Ordinary request cancellation keeps its existing detach behavior.

## Risks

Cancellation settlement may exceed the worker's request timeout while authentication's existing bounded exchange/persistence completes. This is intentional to prevent losing rotated credentials or closing resources beneath the refresh. PostgreSQL contention tests must exercise an uncommitted replacement, not only replacement before a query starts.
