## Context

This is the third selective backport onto `feature/multi-file-account-import`, cut at `4940aad2` after round 2 was merged and deployed.

- The peer debate `review-think-20261019-003` reached consensus on the buckets.
- The operator approved the approach on 2026-10-20.
- Planning spikes then showed that two TAKE candidates only affect the HTTP bridge, which production barely uses. The operator deferred both.
- The plan review is `review-plan-20261020-001`.

## Goals / Non-Goals

**Goals:**
- Port the 13 selected fixes so each behaves as upstream intended on the fork.
- Keep the fork invariants intact:
  - native Codex HTTP stays out of the HTTP bridge unless the transport is explicitly `websocket`;
  - the round-2 `reset_evidence` recovery;
  - the settings-based WebSocket payload budget;
  - the fork's warm-up features (new-account warm-up, dashboard warm-up settings, staggered idle);
  - capacity replay and early owner publication;
  - account-neutral source routing.

**Non-Goals:**
- The release merge, migrations, new settings, dependency bumps.
- The HTTP-bridge continuity family: #2247, #2386, #2387, #2384, #2390, #2397.
- WebSocket connect-time fresh replay for `previous_response_owner_unavailable`, which is a separate fork follow-up.
- Merge, push, deployment or archiving.

## Decisions

- **One coherent commit per fix, with provenance.**
  - Each upstream commit is applied with `git cherry-pick --no-commit`.
  - Upstream `openspec/**`, `.all-contributorsrc` and README hunks are dropped.
  - Adaptations are folded in before committing.
  - The message records `(cherry picked from commit <sha>)` plus `Adapted:`/`Omitted:` lines.
- **#2205 is taken as-is.**
  - No pacing, setting or runtime-state change.
  - The first refresh cycle after deploy is expected to send ~1,800 initial warm-ups serially. Production data on 2026-10-19: 1,812 opted-in never-attempted active Free accounts, all at 0% monthly use; mean send 2.7 s; failure baseline ≈2.07%.
  - The PostgreSQL advisory-lock rolling test cannot run on this host and is recorded as not run.
- **#2233 adaptation:**
  - Upstream's `monthly_reset_evidence` is the fork's `reset_evidence`, so only `dashboard_settings=` is added.
  - The `background_recovery_state_from_account` docstring addition is one line, so `load_balancer.py` stays at 3021 lines.
  - Upstream MODIFIES two `account-routing` requirements the fork does not have, so this change ADDS a narrower requirement for the background builds.
- **#2113 test adaptation:**
  - The fork has no `MAX_SSE_EVENT_BYTES` constant, and `_ws_transport_payload_budget_bytes` takes `settings`. The upstream test uses the settings value instead.
  - Production code is verbatim.
- **Test-only conflicts** keep the fork's lines plus this commit's own lines. Lines from other, unported upstream commits are dropped: `_disable_background_loop_schedulers` in `tests/conftest.py`, and the model-source dialog smoke test from #2059.
- **Deferred #2387** (denied-anchor refusal to native clients):
  - The bug needs native Codex HTTP inside the HTTP bridge.
  - The fork excludes it unless the transport is explicitly `websocket` (`streaming/retry.py:225-228`), and production runs `auto`: 0 native Codex requests went through the bridge in 7 days.
  - Its upstream tests hang on the fork because they assume #2247's promotion.
- **Deferred #2384** (continuity replay attribution): its metric and request-log rows are HTTP-bridge only. The bridge served ~114 requests in 7 days, while the 800 weekly `previous_response_owner_unavailable` errors are direct WebSocket.

## Risks / Trade-offs

- **Initial warm-up burst:** bounded by the serial refresh loop and the durable no-prior-attempt guard. Watched for 24 h after deploy (see `context.md`).
- **Anonymous frame ownership:** only the exactly-one-created case changes. Other counts keep the existing matching.
- **SQL read shape (#2235):**
  - SQLite tests compare against a raw oracle for every watermark position.
  - The PostgreSQL `EXPLAIN` probe is not run on this host.
- **Test environment:**
  - this host runs production, so only serial targeted files run, against a temporary SQLite DB;
  - frontend checks are scoped to the touched files, plus one browser smoke run;
  - the full CI matrix, PostgreSQL-only tests and the image build are not run here.

## Migration Plan

- No database migration.
- Deploy through the HA surge rollout when requested.
- Rollback is a code revert or the previous image. Warm-up attempt rows already written stay.

## Open Questions

None blocking.
