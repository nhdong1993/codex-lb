# Verification: prompt plan downgrade confirmation

Verified locally on 2026-10-02. Implementation and specifications are complete. Production was not migrated or deployed, and no account credentials or status were changed during implementation. Existing unrelated workspace changes were retained.

Subsequent adversarial review found four gaps not covered by this original test slice: PostgreSQL replacement contention, reused WebSocket exclusion, reopening completed work for new Free evidence, and OAuth settlement on cancellation. See the [follow-up verification](../2026-10-02-harden-priority-plan-verification/verification.md) for fixes and additional regression evidence. The original results below describe the earlier verification snapshot.

## Requirement coverage

| Requirement | Implementation and evidence |
| --- | --- |
| Bounded shared priority verification | `app/modules/usage/plan_checks.py`, `plan_check_scheduler.py`, `updater.py`; integration coverage for 15-second first-Free scheduling, shared coalescing/claim contention, three-attempt budget, three-worker fan-out, endpoint partial failure, unknown responses, paid contradiction and cancellation cleanup. |
| Credential and authentication ownership | Generation and refresh-credential guards in the usage updater, observation store and account metadata writer; tests for in-flight replacement, stale permanent failures, preserved routine rotation, workspace ambiguity, transient refresh failures and explicit permanent refresh errors. |
| Temporary account/model routing exclusion | Shared evidence read during load-balancer selection; HTTP streaming and WebSocket failover tests exercise the actual request surfaces. Integration tests cover unrelated models, expiry, required file ownership and continuity ownership. Account-health handling stays separate. |
| Pending subscription presentation | Account/dashboard summary flag and shared subscription component; account GET and trailing-slash summary tests, component/cache/hook tests, and List/Grid/Detail browser checks at 1440px and 375px. |
| Existing subscription behavior | Existing API/rotation tests and frontend hook tests cover throttle, inactive snapshot suppression, historical metadata, manual response merging and ownership. Priority checks call the same subscription service. |
| Additive migration | Single head after `20260929_000000_add_source_websocket`; SQLite and PostgreSQL round trips preserve historical plans/status/credential bytes and report no schema drift. Foreign key uses account deletion cascade; import/reauth cleanup shares the credential replacement transaction. |

## Checks performed

- **616 passed:** unit load-balancer, contract, concurrency, virtual-clock, usage-updater and downgrade-observation suites.
- **50 passed:** SQLite integration priority checks, accounts repository, multi-replica load balancer and new migration round trip.
- **16 passed:** final priority-check integration suite against an isolated PostgreSQL 18 database.
- **17 passed:** earlier PostgreSQL run combining the initial priority checks and durable downgrade-observation store; later added priority cases are covered in the 16-case final run.
- **1 passed:** PostgreSQL migration upgrade/downgrade/upgrade with historical credentials and schema drift checks, in a separate isolated database.
- **15 passed:** priority checks plus selected HTTP model-entitlement failover and WebSocket stale-account/model failover regressions (before the final three priority cases were added).
- **152 passed:** subscription/new migration, durable observation and usage-updater regression slice.
- **101 passed:** Force Probe, auth-manager, subscription refresh and initial priority-check regression slice.
- **45 passed:** frontend subscription component, subscription-response cache and account hook tests.
- **3 passed:** browser checks for List, Grid and Detail, each at desktop/mobile widths; screenshots show the simulated stored deadline before verification and the pending state after it. No horizontal overflow. This compares two fixture states in the updated build, not production screenshots.
- Frontend TypeScript check, targeted ESLint and Vite production build passed.
- Targeted Ruff lint and formatting checks passed; `git diff --check` passed.
- Proxy architecture, cancellation safety, timing seam and settings tier checks passed without increasing architecture thresholds or adding operator settings.
- Change strict validation passed; all **67 main specifications** passed strict validation after syncing.
- Isolated SQLite migration CLI check reported the intended head, valid migration policy and no drift. The temporary PostgreSQL test container was removed after verification.

## Remaining limits

No missing implementation requirement was found. Repository-wide `ty check` still reports two diagnostics outside this change: the existing workspace edit at `tests/integration/test_proxy_chat_completions.py:109` supplies a dictionary where `OpenAIErrorEnvelope` is expected, and the unchanged `tests/unit/test_key_dashboard_install.py:204` assigns an incompatible `JsonValue`. These were not modified. This report does not claim a clean whole-repository type gate, complete CI, or production validation.

The worker shares the background-usage enablement setting. A large batch or slow upstream can delay confirmation; after bounded attempts expire the ordinary fleet scan remains the fallback. An upstream outage can leave old successful metadata available after the pending indicator expires. Only the latest rejected model is retained during each two-minute request window. Revoked tokens still require reauthentication; plan verification cannot repair upstream credentials. Mixed-version replicas do not all provide this behavior until rollout completes.

## Visual evidence

- List: [before desktop](evidence/before-list-1440.png), [after desktop](evidence/after-list-1440.png), [before mobile](evidence/before-list-375.png), [after mobile](evidence/after-list-375.png).
- Grid: [before desktop](evidence/before-grid-1440.png), [after desktop](evidence/after-grid-1440.png), [before mobile](evidence/before-grid-375.png), [after mobile](evidence/after-grid-375.png).
- Detail: [before desktop](evidence/before-detail-1440.png), [after desktop](evidence/after-detail-1440.png), [before mobile](evidence/before-detail-375.png), [after mobile](evidence/after-detail-375.png).

Main specs and stable context are synced for `usage-refresh-policy`, `account-subscription-term`, `account-routing` and `database-migrations`. Archive is appropriate with the unrelated typecheck limitations above recorded; deployment remains a separate operator action.
