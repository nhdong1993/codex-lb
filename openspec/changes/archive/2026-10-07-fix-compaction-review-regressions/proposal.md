## Why

Review of source compaction reproduced two regressions: a broken upstream TCP
stream escapes as HTTP 500 and a cancelled log, while conversion to the Responses
schema rejects subscription compact extras before routing (for example,
`conversation: {"id": "conv_existing"}`). The previous compact handler accepted
the same subscription request.

## What Changes

- Convert transport failures during compact collection to a 502 source error,
  with error logging, exactly-once cleanup and no replay of a consumed stream.
- Resolve compact routing and subscription continuity on the compact request
  before applying the source Responses schema. Preserve source ownership and
  disabled-source checks when source lookup misses.
- Add regressions at both standalone compact endpoints.

## Capabilities

### Modified Capabilities

- `model-source-routing`: subscription compact validation retains its contract.
- `responses-api-compat`: compact stream transport failures produce upstream errors.

## Impact

Scoped routing/collector corrections and integration coverage. No new setting,
provider special case, schema migration, deployment or credential change.
