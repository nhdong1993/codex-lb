# Verification: refresh-account-subscription-term

Verified on September 28, 2026. Implementation is complete and the changed requirements and context are synced to `openspec/specs/account-subscription-term/`.

| Dimension | Result |
| --- | --- |
| Completeness | All implementation and validation tasks complete; three delta requirements implemented |
| Correctness | Renewal, source replacement, inactivity, duration boundaries, partial failure, route refusal, concurrent replacement and historical-row scenarios covered |
| Coherence | Follows the planned endpoint-local transport, shared snapshots, leader scheduling, independent sessions and conditional writes |

## Requirement evidence

- Account summaries: `app/modules/accounts/mappers.py` prefers matching snapshots and labels their source. `tests/integration/test_subscription_refresh.py` verifies renewed October 4 metadata on account list, summary and trailing-slash summary paths, including paused accounts. GETs do not call upstream. Inactive results suppress token fallback; failed refreshes preserve successful metadata; changed credentials invalidate old results.
- Compact duration: `frontend/src/features/accounts/components/account-subscription.tsx` uses one unpadded days/hours format across all variants. Component tests cover `5d 8h`, periods below one hour, elapsed and unknown states, source labels and the shared clock. Browser coverage exercises Detail, List and Grid at desktop and mobile sizes, management dialogs and sorting.
- Background refresh: `app/core/clients/subscriptions.py`, `app/modules/accounts/subscription_repository.py` and `subscription_scheduler.py` implement the specified headers, browser transport, route resolution, timeout, persisted throttle, ownership checks and bounded workers. Tests cover malformed payloads, HTTP errors, credential/identity/plan changes, superseded attempts, deletion/deactivation, partial failure, follower behavior and cancellation cleanup.
- Historical rows: `tests/integration/test_subscription_migration.py` verifies upgrade, preserved credentials/status, null snapshot columns, downgrade and re-upgrade. The isolated SQLite database reports the intended migration head and no schema drift.

## Checks

- Subscription client, dashboard API and refresh tests: 59 passed.
- Existing account/authentication regression tests: 60 passed.
- Migration tests: 5 passed; migration policy valid and schema drift absent.
- Frontend subscription, list and schema tests: 41 passed.
- Browser scenarios: 3 passed, with synthetic screenshots under `evidence/`.
- Frontend lint, TypeScript and production build passed.
- Targeted backend Ruff and type checks passed, along with proxy architecture, cancellation safety and timing seam checks.
- Strict change validation passed; strict validation of all 66 main specs passed.
- `git diff --check` passed.

Before images are retained in `../2026-09-27-compact-account-list-plan-badge/screenshots/` after archive; the updated desktop/mobile Detail, List and Grid images are in this change's `evidence/` folder. Screenshot data is synthetic.

## Live source check and limits

A read-only request using the new client and the existing configured account proxy returned `2026-10-04T04:36:34+00:00`, matching the operator's reported October 4 subscription renewal. No credentials or raw response bodies are recorded here. The live check did not write subscription data or run a production migration.

Validation covered the focused backend suites and SQLite migration round-trip; it did not run the entire backend suite or a PostgreSQL migration round-trip. No deployment was performed as part of this change. The additive migration and normal application startup will enable the background refresh when deployed.

No critical findings or known requirement deviations remain. Ready for archive.
