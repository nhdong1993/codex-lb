## Context

The snapshot fingerprint includes access-token ciphertext. Auth Guardian rotates tokens after twelve hours of age, while subscription attempts are throttled for twenty-four hours. Manual refresh currently cancels reads only at request start and observes only the most recently triggered mutation.

## Goals / Non-Goals

Preserve verified subscription data and correct pending controls under rotation and concurrent requests. Keep credential replacement guards, daily cadence, schema and API responses unchanged.

## Decisions

- Rebind only a currently matching snapshot inside the existing token rotation transaction when identity and plan stay the same. Keep credential compare-and-set and guard the rebind against concurrent source changes. Do not weaken fingerprint binding globally: that would trust snapshots after arbitrary credential replacement.
- Cancel account-list reads again immediately before merging successful manual subscription fields. A cancellation prevents older responses publishing into the query cache; later polls remain authoritative without a second persistent cache.
- Give subscription mutations a stable key and derive all pending account IDs from the query client's mutation cache. Avoid duplicating mutation lifetime in component state.
- Cover API list/summary after repository token rotation, controlled deferred polling, and independently resolving/rejecting refreshes. Capture List pending states with synthetic accounts.

## Risks / Trade-offs

- Token persistence is sensitive: preserve its refresh-token CAS and test failed rotation and changed identity/plan alongside the successful path.
- Requests may settle in any order: cancellation runs before the local merge; tests retain newer data and exercise later authoritative reads.
- Existing invalidated snapshots stay ignored until the usual refresh; the change does not invent dates or reset the daily attempt clock.

## Migration Plan

No additional migration or settings. Ship with the existing subscription feature after local verification. No runtime data edits are required.
