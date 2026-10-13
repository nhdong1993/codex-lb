# Design

## Configuration

Add `model_plan_routing_policies: dict[str, list[str]]` to dashboard settings and persist it as serialized JSON in one non-null Text column with an empty-object default. Validate exact nonempty subscription model IDs, nonempty plan lists, and recognized plan IDs using the existing plan-type module. Do not derive policy from model-source display names or rewrite upstream `available_in_plans`. Removing a model key restores the existing flow. Omitted PUT fields preserve the mapping; an explicit empty object clears it.

## Selection

Resolve the request's subscription model identity after the existing source/subscription dispatch. Intersect routing candidates with configured normalized plans, existing API-key scopes, model entitlements, health, quota, and other gates. Keep existing ranking among the surviving candidates. If a configured pool is empty, return the existing routing error envelope without falling back to a different plan.

Keep continuity-owner discovery and sticky-mutation authority separate from routability. A pinned owner that fails the configured policy must fail closed; filtering must not manufacture a different owner. The same policy must govern bridge/websocket reuse and retries. Incorporate policy changes into selection cache keys/invalidation and normal settings propagation across replicas.

## Implementation sequence

1. Trace subscription dispatch, selection, strict owners, and connection reuse before choosing the shared policy helper boundary.
2. Add the single-head migration, typed settings contract, serialization, PUT handling, and validation.
3. Integrate the eligibility restriction and cache invalidation, then cover ownership and retry paths.
4. Add the mapping editor under existing routing settings, using subscription catalog entries only.
5. Validate API, migration, routing, WebSocket, frontend, and OpenSpec behavior; sync author-verified requirements and stable context before independent review so the combined diff is reviewed. Independent review and archive remain separate pending gates; do not archive during author integration.

## Admission and identity decisions

Plan equality is strict normalized membership in `free`, `plus`, `pro`, `prolite`, `team`, `business`, `enterprise`, or `edu`; entitlement equivalences do not widen operator restrictions. Exact effective subscription model IDs are matched after existing alias/API-key handling. IDs may be preconfigured without live catalog membership. Null, like omission, preserves the mapping; only `{}` clears it.

Use one pure evaluator and strict parser. Invalid persisted JSON or settings-read failures fail closed with a sanitized local admission error. Selection uses a coherent settings snapshot and deterministic policy cache fingerprint even for direct load-balancer callers. Filter only routing candidates after owner discovery, before additional-quota filtering, including its reauthentication fallback.

Compose connection policy checks with model admission, not the compatibility helper with early returns. Cover bridge cached/alias lookup, retained handoff, creation future, return-after-close, final submission after waits, and direct WebSocket reuse/final admission. Read current account plans rather than socket-open snapshots. Keep database I/O outside the bridge registry lock and preserve accepted siblings, reservation settlement and task ownership when rejecting unsent work. Policy exclusion never authorizes guarded owner abandonment.

## Author integration status

The original backend/frontend implementation and the concurrent direct native
HTTP final-send/same-account retry correction are integrated. The 2026-10-13
integration pass verified that correction at the product routes, narrowed the
final direct-send recheck to configured models (persisted plan only, no
plan-check query), kept settings readable and repairable when the stored
mapping is invalid, removed the dead dashboard additional-quota loader, gave
stub-repository unit tests an explicit empty policy snapshot, and moved
head-pinned migration tests to the new head. Exact commands and results are in
verification.md. The architecture check now passes without budget changes.
These author checks are evidence, not independent approval. No production
settings, database, deployment, or runtime state was changed, and neither
change is archived.
