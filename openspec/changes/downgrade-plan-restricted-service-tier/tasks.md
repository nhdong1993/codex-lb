## 1. Specification

- [x] 1.1 Write proposal, context, tasks and the `account-routing`, `chat-completions-compat` and `responses-api-compat` deltas. Run `openspec validate downgrade-plan-restricted-service-tier --strict`.

## 2. Tests first

- [x] 2.1 Unit, `tests/unit/test_model_plan_service_tier_fallback.py`:
  - drop for `priority` and `fast`;
  - drop when the recognized model advertises no tiers;
  - keep when an allowed Plan offers the tier, for an unconfigured model, without a snapshot, with a non-authoritative snapshot, for an unknown model, and when the policy lookup fails;
  - no settings read for omitted, `auto` or `default` tiers.
- [x] 2.2 Integration, `tests/integration/test_model_plan_routing.py`:
  - both Responses paths, stream and non-stream, with `priority` and `fast` → a Free account and no wire tier;
  - Chat Completions and compact → the same;
  - unconfigured model → tier kept, routed to the account that offers it;
  - `["free", "plus"]` → tier kept.
- [x] 2.3 Websocket, `tests/integration/test_proxy_websocket_account_availability.py`: real connector and load balancer → a Free account and no tier in the upstream frame.
- [x] 2.4 Source isolation, `tests/integration/test_model_plan_source_isolation.py`: a same-slug source keeps `priority` under catalog evidence that would downgrade the native model.
- [x] 2.5 Confirm the new regressions fail before the implementation.

## 3. Implementation

- [x] 3.1 Add `apply_model_plan_service_tier_fallback` in `app/modules/proxy/request_policy.py`.
- [x] 3.2 Call it at the five preparation sites: `_stream_responses` (non-forwarded branch), `_collect_responses`, Chat Completions, compact, websocket preparation.

## 4. Verification and sync

- [x] 4.1 Run the targeted suites sequentially, plus ruff, ruff format and ty on the touched files.
- [x] 4.2 Run `/review-impl`.
- [x] 4.3 Sync the deltas into the main specs and the `account-routing` context. Run `openspec validate --specs`.
- [ ] 4.4 Archive after the operator accepts the result.
