## Why

Production catalogs still advertise `multi_agent_reasoning_effort: "xhigh"` for subscription `gpt-6.1-sol`, so Codex selecting Ultra sends xhigh. The existing max override only covers `gpt-6-astra`.

## What Changes

- Extend the existing outgoing catalog override to subscription `gpt-6.1-sol` when it supports both max and ultra.
- Keep native, versioned compatibility, and installer catalogs consistent while preserving stored upstream metadata and explicit request efforts.
- Extend public-route regression coverage and document client catalog refresh requirements.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-catalog-compat`: Extend the Astra Ultra effort policy to GPT-6.1 Sol.

## Impact

Touches the shared Codex catalog serializer, API tests, and OpenSpec documentation. No new setting or migration is needed. Production deployment and refreshing pinned client catalogs are required for existing clients to receive the new policy.
