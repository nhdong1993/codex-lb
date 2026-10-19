## Why

Upstream (`Soju06/codex-lb` `origin/main`) has 188 commits since the fork's merge base `v1.25.0-beta.6`. A full release merge is not viable now. It means 115 conflicted files, the dashboard auth rewrite, about 35 migrations, and column drops that are not safe for the active-active surge rollout. Several upstream fixes, however, close real gaps on the production fork:

- the locked native TLS stack (rustls 0.23.45) and urllib3 2.7.0 carry published advisories;
- HTTP-bridge replays can spin for the whole 7200 s budget on an owner the caller itself excluded;
- a bridge local recovery reserves API-key quota twice;
- one transient exclusion permanently rebinds a prompt-cache thread;
- safety-policy blocks count against the account;
- a deactivated workspace is neither excluded nor failed over;
- a paid account benched by a 429 stays benched after its window resets early;
- the GPT-6 family advertises no output budget.

This round ports a user-selected set of those fixes without the schema removals, settings migration or auth rewrite, and without replacing fork behavior.

## What Changes

- **A (security/deps):**
  - rustls 0.23.46 (RUSTSEC-2026-0346..0349, upstream #2622);
  - urllib3 2.8.0 floor and lock (CVE-2026-97687/97689, #2588/#2595);
  - Debian runtime package upgrades in the image (#2407).
- **C (model metadata):**
  - GPT-6 `max_output_tokens` fallback 128000, including the fork-only `gpt-6.1-sol` (#2528);
  - `codex_cli_rs` UA counted as the `codex-cli` telemetry family (#2517);
  - edge-case tests for source base instructions (#2525, tests only);
  - fork fix: the fallback Codex client version becomes `0.163.0`, at least every bootstrap `minimal_client_version`.
- **B (routing/proxy reliability):**
  - soft TTL-bounded sticky owners survive request-local unavailability (#2234), with the fork's backoff and plan-admission rebind rules kept;
  - an excluded hard owner is not waited on (#2381);
  - bridge local recovery reuses its reservation (#2353);
  - a bridge model-transition owner conflict forks a guarded child lane (#2083);
  - `misalignment_policy_violation` safety blocks are account-neutral (#2131);
  - `deactivated_workspace` deactivates only the selected record and fails over when movable, with keyed health written after settlement on both the first-dispatch and post-refresh paths (#2573, fork extension);
  - HTTP response owners are published on the same replica before delivery, never for capacity-replayed attempts (#2111, fork adaptation);
  - typed file-failover provenance (#2469);
  - reset-confirmed recovery of rate-limited accounts on any deadline-matched window (#2405);
  - force-probe settlement from snapshotted rows (#2524);
  - prompt deletion-worker stop (#2362);
  - shared-future exception consumption (#2427);
  - retained immediate cache invalidations (#2545).
- **Not taken:** #2360 (bare `server_error` overload weight) and #2408 (retain soft owners through overload isolation) contradict fork policy; #2386 is deferred; #2525's code already exists in the fork; the pricing-snapshot refreshes depend on an absent upstream feature.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `outbound-http-clients`: patched rustls and urllib3, runtime Debian upgrades, fallback client version floor.
- `model-catalog-compat`: GPT-6 max output fallback with catalog precedence.
- `telemetry`: `codex_cli_rs` client family.
- `graceful-shutdown`: deletion worker stop.
- `proxy-runtime-observability`: abandoned shared waits.
- `query-caching`: retained immediate invalidation bumps.
- `usage-refresh-policy`: any-window reset recovery, force-probe snapshot, workspace deactivation in refresh.
- `account-routing`: reset recovery across replicas, safety-block neutrality, deactivated workspace failover and settlement order.
- `sticky-session-operations`: request-local soft-owner spillover, excluded hard owner, reservation reuse.
- `responses-api-compat`: early same-replica owner publication, bridge model-transition fork, typed unary file failover provenance.

## Impact

- Rust manifest and lockfile, Python manifest and lockfile, `Dockerfile`.
- Proxy load balancer, sticky selection, streaming retry/helpers/mixin, websocket mixin, HTTP bridge streaming, file proxy, usage refresh scheduler, cache invalidation, shared-future helper, account deletion worker, telemetry, `/v1/models` metadata, settings default and its generated reference doc.
- No migration, no new setting, no UI change, no package version change.
- Runtime effects on persisted state:
  - accounts hitting `deactivated_workspace` become `deactivated`;
  - `rate_limited` accounts can return to `active` earlier when a reset is confirmed;
  - prompt-cache sticky rows are rebound less often.
- Rollback is a code revert or redeploying the previous image. Status rows already written stay as written.
