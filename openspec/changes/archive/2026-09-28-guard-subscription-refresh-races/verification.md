# Verification

## Scope and completeness

Both second-review findings are resolved: matching first/repaired snapshots committed between token rotation's read and write survive the atomic token update, and delayed manual responses cannot replace a newer source or newer metadata in the account cache.

All six tasks are complete. Both modified requirement blocks are synchronized to the main subscription-term spec; context explains the source guards, timestamp policy, constraints and examples.

## Correctness evidence

- Before the fix: four deterministic late-save cases failed through dashboard list/summary reads (absent/unmatched old snapshot, paid/inactive incoming result). Six concurrent replacement/CAS tests passed.
- After the fix: **119 backend tests passed** across subscription refresh, token refresh claims and AuthManager. Concurrent access credential, refresh credential, ChatGPT account, plan, user and workspace replacement still prevents unauthorized transfer. Check and daily-attempt times remain unchanged, with no extra upstream fetch.
- Before the fix: nine delayed-response hook scenarios failed (free/paid Plan change, ChatGPT identity, email, workspace, legacy workspace label, newer credential refresh, newer paid check and newer inactive check). Matching-source subscription-only merge passed.
- After the fix: **71 frontend tests passed** across account hooks, page, list, overview row and subscription component. Unrelated alias, workspace label for a known workspace, status, policy and quotas remain current on a successful merge. Previous stale-poll and per-account pending regressions remain green.
- Browser: **5 tests passed**, covering the delayed Plus-to-Free response, concurrent pending/error behavior across views, and desktop/mobile Detail, List and Grid layouts. The same delayed-response test failed against the pre-fix build at the final visible term assertion. Before/after screenshots are in `evidence/`; the corrected row shows Free with No data after the response arrives.

## Checks

- Changed Python Ruff check and format check: passed.
- Targeted Python ty check: passed.
- Full frontend ESLint: passed.
- TypeScript and production frontend build: passed.
- Strict change validation: passed.
- Strict main-spec validation: **66 passed, 0 failed**.
- `git diff --check`: passed.

## Coherence and limits

Snapshot permission is tested in SQL against the computed old credential fingerprint, not the earlier snapshot's stored fingerprint. The mandatory refresh-token CAS and concurrent identity guards remain in place. The frontend keeps one authoritative query cache and checks existing public source/timestamp metadata; credentials are never exposed. No schema, API response, setting or cadence change is required.

Validation used synthetic accounts, local databases and mocked browser HTTP responses. No production write, commit, push or deployment was performed. No unresolved verification findings remain for these two changes.
