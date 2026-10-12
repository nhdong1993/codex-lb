# Verification: reroute-soft-affinity-on-upstream-backoff

Verified locally on 2026-10-12. No application deployment, commit or push.

## Summary

| Dimension | Result |
| --- | --- |
| Completeness | Implementation, focused tests, main-spec sync and strict validation complete |
| Correctness | Three modified requirements mapped to selection logic and regression coverage |
| Coherence | Reuses existing backoff evidence, replacement selection, caps and provisional sticky writes; no setting/schema/replay changes |

## Evidence and coverage

- `app/modules/proxy/_load_balancer/overload_backoff.py`: the sustained predicate excludes burst-only cooldown, and the soft-owner replacement pool now uses the sustained deadline rather than requiring isolation.
- `app/modules/proxy/_load_balancer/sticky_selection.py`: earlier rerouting keeps the existing eligibility, budget, cap, probe-pool and sticky-rebind machinery. Hard-owner dispatch remains outside this soft-owner path.
- `tests/unit/test_overload_backoff.py`: three-failure threshold, decay/expiry, all three soft sticky kinds, hard required owner, burst-only owner retention, unavailable siblings, cap-exempt owners and capped spillover. Existing isolation variants remain covered.
- `tests/integration/test_proxy_overload_soft_affinity.py`: both public HTTP route families, overload and qualified processing-error messages, interleaved successes, later independent request moves to a sibling, and no implicit replay of terminal requests.
- Focused existing retry tests cover overload classification and keyed reservation settlement before health writes. Existing file-pin and required-owner/concurrency tests cover ownership and cap boundaries.

Completed checks (counts overlap; do not sum as unique tests):

| Check | Result | Local evidence |
| --- | --- | --- |
| Complete overload unit file, new routing integration, HTTP-only guard and mixed-key regression | 84 passed | `/tmp/codex-upstream-http-verified.log` |
| Required-owner/concurrency selection with isolated DB initialization and new route tests | 39 passed, 95 deselected | `/tmp/codex-upstream-owner-final.log` |
| Focused upstream retry, no-replay and settlement/health ordering | 8 passed, 53 deselected | `/tmp/codex-upstream-retry-focused.log` |
| External file-pin regression selection | 4 passed, 27 deselected | `/tmp/codex-upstream-file-pin-tests.log` |
| Ruff lint and formatting of eight touched Python files across both fixes | Passed | Local CLI output |
| `ty check` on three changed production modules across both fixes | Passed | `/tmp/codex-upstream-typecheck.log` |
| `git diff --check` | Passed | Local CLI output |
| Strict main-spec validation | 67/67 valid | `/tmp/codex-upstream-specs-current.json` |
| Strict change validation | Valid | `/tmp/codex-upstream-change-validation.json` |

The delta requirement blocks were compared against main specs and match. Operational context documents first-trip rerouting, hard ownership and replica-local limitations. Existing unrelated working-tree edits were preserved.

## Warnings and limits

- A broader retry/multi-replica/concurrency invocation stopped making progress after 19 cases and was terminated. It is **not** counted as passing, and its cause was not established. Re-run that broad selection before claiming full regression coverage; the focused checks above completed.
- Earlier runs exposed an incorrect new-test argument and stale expectations; those were corrected before the final 84-case run. A standalone owner/concurrency invocation lacked the database initialization now required by other working-tree changes; the initialized 39-case invocation passed.
- This is replica-local routing mitigation, not a fix for provider-wide generation slowness. The incident sample contained 241 overload/processing errors across 13 accounts; moving affinity helps only when an eligible healthier sibling exists. Accepted turns and account-owned continuity are not moved or replayed.
- Code has not been deployed. Archive denotes verified local implementation, not production recovery or satisfaction of GitHub merge gates.

No critical implementation or focused-scenario gaps found. Ready to archive with the broad-regression limitation recorded.
