# Verification

## Scope

Three review findings: verified subscription loss during routine token rotation, older account polling replacing manual refresh results, and last-mutation-only pending indicators. Existing unrelated working-tree changes remain outside this fix.

## Completeness and correctness

- Matching successful and explicitly inactive snapshots survive two same-identity token rotations through dashboard list and summary routes; original check/attempt times stay unchanged and the daily scheduler makes no extra request.
- Changed plan/identity, replaced credentials and a lost token compare-and-set do not authorize reuse. Existing in-flight source guards, account claim and AuthManager concurrency regressions remain green.
- Deferred manual refresh plus an older list response retains the successful term; a later authoritative read still updates paused/free state and removes subscription data.
- Concurrent mutations retain both pending IDs, independently clearing success or failure. Browser checks cover List, the management dialog, Grid and selected Detail while the other account remains pending.

## Evidence

- Backend: `tests/integration/test_subscription_refresh.py tests/integration/test_token_refresh_claims.py tests/unit/test_auth_manager.py` — **109 passed**.
- Frontend: account hooks, page, list, overview row and subscription component suites — **61 passed**.
- Browser: `frontend/screenshots/account-grid.spec.ts` — **4 passed**, including desktop/mobile layouts and concurrent refresh transitions.
- The browser regression fails against the pre-fix build because account A becomes enabled after refreshing B. Its before screenshot and the corrected pending-state screenshots are in `evidence/before/` and `evidence/after/`.
- Ruff check/format on changed Python files, targeted ty check, full frontend ESLint, TypeScript and production build all passed.
- Strict change validation passed. Strict main-spec validation: **66 passed, 0 failed**. `git diff --check` passed.

## Coherence and limits

The database rebind stays inside token rotation's existing guarded transaction and only updates the fingerprint. No new schema or settings. The frontend uses the existing mutation cache and cancels stale query publication without keeping a second subscription cache. Main requirements and context are synchronized. All new scenarios have focused coverage; no outstanding verification findings.

Tests and screenshots use synthetic accounts and local test databases. No production changes, commit, push or deployment were performed.
