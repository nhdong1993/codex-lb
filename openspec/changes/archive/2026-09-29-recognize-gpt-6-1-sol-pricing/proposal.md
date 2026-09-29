## Why

`gpt-6.1-sol` does not match the native pricing catalog, leaving request costs unrecognized and cost-based API-key accounting at zero. It needs its own rates because cached input is cheaper than `gpt-6-sol`.

## What Changes

- Recognize canonical, case-insensitive, and suffixed GPT-6.1 Sol names with a dedicated price entry.
- Apply published Standard, Fast/priority, Flex, and long-context token rates through the existing shared cost calculation.
- Cover request-log API costs, aggregates, API-key reservations, and settlement with regression tests.
- Document pricing provenance and historical-data behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-keys`: Recognize GPT-6.1 Sol token prices for request costs and quota accounting.

## Impact

Changes the static pricing catalog and focused tests. No API/schema changes, runtime settings, dependencies, database migrations, or historical cost rewrites are required.
