# Context: downgrade the service tier for Plan-restricted models

## Purpose

Operator Plan restrictions (`modelPlanRoutingPolicies`, see `configure-subscription-model-plan-routing`) are an intersection: a configured model may only use accounts of the listed Plans. Selection also narrows the pool to accounts whose catalog offers the requested service tier. When the allowed Plans never offer that tier, both filters together leave nothing, and the request fails even though the allowed accounts could serve it at the default tier.

## Incident (2026-10-20)

- Production mapping: `{"gpt-5.6-terra": ["free"], "gpt-6-luna": ["free"]}`.
- Codex Desktop with Fast mode on sends `service_tier: "priority"`. In the authoritative registry snapshot, `priority` for `gpt-6-luna` is advertised only by the 27 Plus accounts; the 3008 Free accounts carry the model without any tier.
- Every `no_accounts` row for `gpt-6-luna` had `requested_service_tier = priority`. The client saw "No available accounts. Service is operating in degraded mode: all upstream accounts are unavailable".
- Fast requests on Free accounts that slipped through earlier came back with `actual_service_tier = default/auto`, so dropping the tier loses nothing the Free Plan offered.

## Decision

Drop the tier from the effective request instead of failing, but only for configured models and only when the catalog positively says no allowed Plan offers the tier.

The helper `apply_model_plan_service_tier_fallback` (`app/modules/proxy/request_policy.py`) removes `service_tier` only when all of these hold:

1. The canonical tier is not empty, `auto` or `default` (`fast` canonicalizes to `priority`).
2. The routing policy can be read. On a lookup failure the tier is kept, and selection fails closed with its existing sanitized error.
3. The exact effective model ID is a key of the mapping (the same key selection uses; no alias widening).
4. A registry snapshot exists and its account catalogs are authoritative.
5. The catalog recognizes the model (`plan_types_for_model` is non-empty). An operator may configure a model before the catalog knows it; selection does not tier-filter an unknown model, so dropping its tier would only change behavior for no gain.
6. No plan returned by `plan_types_for_model_service_tier` normalizes into the allowed Plans. Plan comparison uses the same strict normalization as the restriction itself (`prolite` does not satisfy `pro`).

These guards are sufficient evidence for the override; they do not reproduce every branch of selection (for example, API-key account scope is still applied later by selection).

### Capability, not availability

If any allowed Plan offers the tier, the tier is kept even when every such account is exhausted or out of the API key's scope. Such a request may still fail, exactly as before. The fallback is never a reaction to temporary unavailability and never a paid-plan fallback.

### Where it runs

After model-source dispatch and API-key enforcement, before reservation, bridge preparation and serialization. It runs at five preparation sites: `_stream_responses` (only for non-forwarded requests), `_collect_responses`, subscription Chat Completions, compact, and Responses websocket request preparation. The outer `/responses` handlers call into `_stream_responses` / `_collect_responses`, so they need no extra call. Mutating the payload there keeps selection, bridge keys, API-key accounting, request logs and the wire payload on the same effective tier, as the existing enforced-tier fallback does.

The websocket call runs before the websocket path decides source ownership. That is safe: the source-ownership decision does not depend on the tier, and a source-owned model is rejected with `model_source_requires_http_transport`, after which the client resends over HTTP, where the fallback runs only after source dispatch.

### Relation to other tier rules

- #1248/#1409 (`apply_enforced_service_tier_model_fallback`) stays unchanged: it removes only an API-key-enforced tier that the model never advertises, and never an explicit client tier. The new fallback is a separate operator override that also covers explicit client tiers, but only for configured models.
- `prohibitFastMode` remains the global switch that removes `priority` for every model. The Plan fallback is per model and evidence based.
- For a configured model the fallback runs after API-key enforcement, so an enforced `priority` or `ultrafast` is dropped too when the allowed Plans do not offer it.

## Logging

Request logs store the effective tier: a downgraded request has `requested_service_tier = null`. The diagnostic info line `model_plan_service_tier_fallback request_id=… model=… removed_service_tier=… allowed_plans=…` keeps the removed tier. Keeping the original tier in a request-log column would need request-log plumbing changes and is out of scope.

## Failure modes

- Policy changes race the helper and selection (each reads the 5-second settings cache). Either the tier was dropped but the pool turned unrestricted (served at the default tier, harmless), or the tier was kept and the pool is empty (the previous failure, transient).
- A non-authoritative snapshot keeps the tier. Selection then uses Plan-level evidence, which is the previous behavior.

## Example

Mapping `{"gpt-6-luna": ["free"]}`, authoritative catalog: `priority` only on Plus.

- Request `{"model": "gpt-6-luna", "service_tier": "fast"}` → a Free account serves it; the upstream payload has no `service_tier`; the log line records `removed_service_tier=fast` and `allowed_plans=['free']`.
- Same request with mapping `{"gpt-6-luna": ["free", "plus"]}` → the tier is kept and a Plus account serves it.
- Request `{"model": "gpt-5.4", "service_tier": "priority"}` with `gpt-5.4` unmapped → unchanged behavior.
