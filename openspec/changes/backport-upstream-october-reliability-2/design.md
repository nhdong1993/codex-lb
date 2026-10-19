## Context

This is the second selective backport onto the production fork branch `feature/multi-file-account-import`, cut at `602f685a`. The first round (`backport-upstream-october-reliability`, commit `1f1529d3`) ported #2453/#2454, #2496, #2119, #2255 and #2449. The commit set was chosen by the operator from upstream `origin/main` `72630bbf`. A peer review (`review-think-20261019-002`) and a plan review (`review-plan-20261019-003`) agreed on the buckets and the fork adaptations below.

## Goals / Non-Goals

**Goals:**
- Port the selected fixes so each behaves as upstream intended on the fork.
- Keep every fork invariant intact:
  - settlement before error-health writes;
  - file pins never cross accounts;
  - excluded accounts leave the selection loop;
  - narrow processing-error isolation;
  - the first-trip soft-owner rebind;
  - capacity replay;
  - account-neutral source routing that keeps its API-key reservations;
  - plan-policy model admission;
  - round 1 usage-limit handling.

**Non-Goals:**
- The beta.9 release merge, the auth rewrite, settings-on-dashboard, pricing automation, migrations, new settings, UI work.
- Cross-replica owner readiness.
- Merge, push or deployment.

## Decisions

- **One coherent commit per fix, with provenance.** Each upstream commit is applied with `git cherry-pick --no-commit`. Upstream `openspec/**`, `.all-contributorsrc` and README hunks are dropped, and adaptations are folded in before committing. The message records `(cherry picked from commit <sha>)` plus `Adapted:`/`Omitted:` lines. No commit leaves a NameError, TypeError or SyntaxError state behind.
- **#2234 soft-owner spillover.**
  - The upstream patch references `owner_overload_isolated`, which the fork renamed to `owner_overload_backed_off`.
  - The fork rebinds on the first sustained-overload trip, so the preservation rule yields to backoff, not only to isolation.
  - `exclude_account_ids` carries the caller's `excluded_ids` only. Owners removed by model or plan admission (`rejected_ids`) still rebind.
- **#2381** keeps both the fork's `hard_affinity_scope_mismatch` and upstream's `hard_affinity_owner_excluded`.
- **#2573 deactivated workspace.** The fork has a second terminal-health site after a forced token refresh (`streaming/retry.py`, post-refresh branch). With no pending penalties, `_drain_pending_post_refresh_penalty_on_terminal` returns without settling. Both sites therefore route `account_unavailable` through `_handle_or_defer_keyed_stream_health`. Other failure classes keep their timing.
- **#2131** keeps the fork's message-aware `_should_penalize_stream_error(code, message)` and its code-less usage-limit predicate. Only the exact code `misalignment_policy_violation` plus the upstream message prefix is neutral; `cyber_policy` routing is unchanged.
- **#2111 owner publication.**
  - It is same-replica only.
  - The fork's capacity-replay prelude hold delays `response.created` until the next non-prelude frame, so publication happens at release.
  - An output-free capacity terminal carries the discarded attempt's ID, so the first-frame publication is skipped when the first frame is a capacity terminal. This reuses the `raise_if_capacity_replay` check shape.
  - The upstream test's `created` case is re-synchronized to the hold. Production buffering is not changed.
- **#2405** drops the upstream-only dashboard-settings snapshot (#2233) and refresh-policy constants (#2261) plumbing, and one test that needs them. The fork's warm-up settings are untouched.
- **#2528** adds `gpt-6.1-sol` (production observed `output_tokens` max is exactly 128000). A catalog-provided value still wins.
- **Fallback client version 0.163.0.** The previous `0.153.4` was below gpt-6-luna's `0.155.0`. Production's live lookup returns `0.163.0`.
- **Dropped:**
  - #2360: bare status-less `server_error` at half weight would count fork-local failures and move warm sessions.
  - #2408: retaining owners through isolation contradicts the fork's rebind requirement.
- **Deferred:** #2386, which needs #2261's zero-argument payload-budget helper.
- **Skipped:** #2525's code, which already exists and would merge into a duplicated keyword argument; the pricing snapshot refreshes, whose files come from #2298.

## Risks / Trade-offs

- Semantic conflicts in the streaming retry and helpers code → route-level regressions for keyed settlement, file pins, safety neutrality on HTTP/WS/bridge, and capacity replay; the round 1 suites rerun.
- Widened shared `_LIFECYCLE_EVENT_TYPES` (queued/in_progress) also feeds the WS and bridge parsers → their full suites run.
- Permanent deactivation from a false positive → only the exact `deactivated_workspace` code triggers it; operators can reactivate from the dashboard.
- Earlier rate-limit recovery → a unique deadline-matched window and the short-window guard are required; compare-and-set status writes stay.
- Test environment → this host runs production: serial targeted files only, a temporary SQLite DB with DB override variables unset, and the native helper built in a 2-CPU disposable container. The full CI matrix, the full image build and Python 3.14 product-path tests are not run here.

## Migration Plan

No database migration. Deploy through the HA surge rollout when requested; a failed surge build aborts before traffic moves. Rollback is a code revert or the previous image. Account status rows already written stay as written.

## Open Questions

None blocking.
