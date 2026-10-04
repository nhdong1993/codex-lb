## Why

Selecting Ultra for GPT-6 Astra in Codex currently sends `xhigh`, because the upstream catalog selects that effort for multi-agent mode. The operator wants Astra Ultra to send `max`.

## What Changes

- Advertise `multi_agent_reasoning_effort: "max"` for subscription `gpt-6-astra` when its catalog supports both `ultra` and `max`.
- Apply the policy consistently to native, versioned compatibility, and installer Codex catalogs without changing stored upstream metadata or explicit request efforts.
- Cover the public catalog routes and document refreshing client catalog caches.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-catalog-compat`: Specify Astra's Ultra effort override at the Codex catalog boundary.

## Impact

Touches the Codex model catalog serializer, API regression tests, and OpenSpec context. No database migration, environment setting, or request-routing change is required. Clients using a pinned catalog need to refresh it after deployment.
