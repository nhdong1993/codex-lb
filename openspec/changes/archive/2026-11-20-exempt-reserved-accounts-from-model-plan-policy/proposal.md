## Why

On the production fork, the dashboard setting "Subscription model plans" (`modelPlanRoutingPolicies`) restricts a native model to some account Plans. A key's reserved accounts are its dedicated capacity, but the restriction removes them like any other account, so the key's traffic moves to the shared pool even while its own accounts are healthy.

## What Changes

- For a request authenticated with the owning key, that key's reserved accounts are not excluded by the operator Plan restriction; the shared pool keeps the restriction and is used when the reserved accounts are unusable.
- Other keys and keyless requests keep the exact baseline result: the owning key gets a separate cached load with `plan_exempt_api_key_id` only for mapped models.
- Admission rechecks read the current reservation with the plan; a released reservation stops the exemption at the next check.
- A continuation whose `previous_response_id` owner lookup missed does not use the exemption (HTTP stream, compact, direct WebSocket).
- HTTP bridge prewarm and replay sends recheck the restriction after their waits for the frame's model and the session key.

No new settings, schema or API fields.

## Capabilities

### Modified Capabilities

- `account-routing`

## Impact

- Code: `app/modules/proxy/{load_balancer,account_cache,model_admission,service}.py`, `_load_balancer/{reserved_accounts,opportunistic_admission}.py`, `_service/{compact,streaming/retry,streaming/mixin,websocket/mixin,http_bridge/mixin,http_bridge/request_submit}.py`.
- Docs: `docs/routing.md`, `docs/api-keys.md`.
