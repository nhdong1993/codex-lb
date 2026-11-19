## Why

An API key can reserve accounts that only it may use, and it prefers them. The model registry's per-model Plan set ("Subscription model plans") still removes a reserved account whose Plan is not listed for the requested model before that preference runs, so the key's traffic silently moves to the shared pool. Operators who dedicate an account to a key want that key to use it regardless of the generic model-to-Plan map, and to fall back to the shared pool only when the reserved accounts are unusable.

## What Changes

- For a request authenticated with the owning key, a reserved account of that key is no longer excluded only because its Plan is outside the requested model's registry Plan set (or outside a service tier's Plan set when that set is just the model's Plan set).
- The exemption does not cover per-account catalog evidence, tier-specific registry data, `ultrafast`, or suppressed/undiscovered models.
- Requests from other keys and keyless requests get exactly the result, error code and message they get today: the owning key's view is loaded separately (one extra cached load, keyed by the owning key id), and the exemption is decided from the reservation read in that same load.
- HTTP bridge session reuse applies the same exemption using the reserved accounts of the API key on the current request.
- Fallback when the reserved accounts are unusable reuses the existing reserved-first preference; the shared pool keeps the Plan filter.

No new settings, schema or API fields.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `account-routing`: reserved accounts of the owning key are exempt from the model Plan filter; strategy requirements reference the exemption.
- `model-catalog-compat`: plan-filtering requirements reference the exemption.

## Impact

- Code: `app/core/openai/model_registry.py`, `app/modules/proxy/_load_balancer/{model_eligibility,reserved_accounts,opportunistic_admission}.py`, `app/modules/proxy/load_balancer.py`, `app/modules/proxy/account_cache.py`, `app/modules/proxy/_service/{support,compact}.py`, `app/modules/proxy/_service/streaming/retry.py`, `app/modules/proxy/_service/http_bridge/{helpers,mixin,activity}.py`.
- Docs: `docs/routing.md`.
