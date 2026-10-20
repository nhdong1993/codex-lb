## Why

Rounds 1 and 2 (`backport-upstream-october-reliability`, `backport-upstream-october-reliability-2`) ported the most urgent upstream fixes onto the production fork branch `feature/multi-file-account-import`. Upstream `Soju06/codex-lb` `origin/main` (`72630bbf`) still carries several smaller fixes that apply to the fork without a migration, a new setting or a release merge. Each one closes a gap the fork actually has:

- a WebSocket session keeps re-injecting a `previous_response_id` that upstream already denied;
- a pipelined upstream socket can hand anonymous output frames to the wrong request;
- one request's detached-bridge sweep can wait 5 s per busy session;
- every Python WSS connect builds a new TLS context;
- HTTP preparation serializes the full payload twice for nothing;
- opted-in Free accounts never receive a warm-up, because their monthly `reset_at` slides;
- dashboard conversation counts scan the whole raw window;
- the weekly-pace aggregate re-runs on every poll;
- operators cannot resume a `deactivated` account from the UI;
- the quota chart draws false drops to zero;
- the quota planner stores invalid timezones and clock times;
- background account-state builds ignore the dashboard soft-drain value.

## What Changes

- **Proxy and clients:**
  - a denied proxy-injected WebSocket anchor is retired (#2248);
  - the detached-sweep lock wait shares one deadline (#2315);
  - anonymous output frames go to the single created response (#2357);
  - Python WSS reuses a cached system-trust context (#2110);
  - unused preparation serialization is skipped (#2113).
- **Warm-up:** an opted-in Free account with a completely unused monthly quota receives one initial warm-up (#2205).
- **Dashboard reads:**
  - the conversation presence raw tail is bounded by index ranges (#2235);
  - the trailing-demand aggregate is memoized for 60 s per process (#2236).
- **UI:**
  - Resume is offered for `deactivated` accounts (#2060);
  - the quota chart interpolates gaps and the usage panel resets per account (#2489).
- **Planner:** invalid timezones (#2468) and clock times (#2540) are rejected.
- **Routing:** the quota planner and usage-refresh recovery build account states from the dashboard snapshot (#2233).
- **Not taken:**
  - **Deferred:**
    - #2387 and #2384: HTTP-bridge-only; the bridge served ~114 requests in 7 days, and native Codex HTTP does not enter it under `auto`;
    - #2247 with #2386;
    - #2390 with #2397;
    - #2246, #1997, #2320, the automation reclaim fix;
    - the dependency bumps.
  - **Skipped:** #2258, #2367, and the already-present hop-by-hop fix.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: denied WebSocket anchor retirement, anonymous output ownership, bounded detached sweep.
- `outbound-http-clients`: shared system TLS context for Python WSS, serialization only for active consumers.
- `usage-refresh-policy`: one initial warm-up for fully unused Free quota.
- `query-caching`: index-bounded conversation raw tail, memoized trailing demand.
- `frontend-architecture`: Resume for deactivated accounts.
- `account-quota-presentation`: faithful trend series, account-scoped panel state.
- `quota-phase-planner`: timezone and clock-time validation.
- `account-routing`: background state builds follow the dashboard snapshot.

## Impact

- **Backend:**
  - WebSocket helpers and mixin, HTTP-bridge helpers and upstream events;
  - outbound HTTP, WebSocket and proxy clients;
  - limit warm-up service and repository, usage refresh scheduler;
  - rollup reads, dashboard repository;
  - quota planner API, logic, schemas and scheduler;
  - the load balancer's background state builder (`load_balancer_lines` stays at its 3021 ratchet).
- **Frontend:** account actions, dashboard list and cards, trend chart, usage panel; one new screenshot spec.
- No migration, no new setting, no dependency change, no package version change.
- **Runtime effects:**
  - On the first refresh cycle after deploy, roughly 1,800 opted-in never-attempted Free accounts receive one warm-up each, serially. This is about 82 minutes of extra send time, and one refresh cycle stretches from about 2 h to 3–4 h.
  - Dashboard reads become cheaper.
  - Planner writes reject invalid input that was accepted before.
- **Rollback:** a code revert or the previous image. Warm-ups already sent and their attempt rows stay.
