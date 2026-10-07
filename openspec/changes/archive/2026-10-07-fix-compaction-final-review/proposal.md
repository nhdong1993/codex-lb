## Why

The final compaction review found two remaining contract gaps. A malformed
usage object at the `response.completed` event root can be replaced by stale
usage observed earlier in the stream, and provider reasoning materialized by
request policy is lost when a compact request is converted to a source
Responses request. The former can settle an invalid response as valid usage;
the latter can send duplicate reasoning aliases that strict providers reject.

## What Changes

- Fail closed on a non-null malformed terminal-root usage object instead of
  falling back to earlier counters, while retaining valid terminal precedence
  and null/absent fallback behavior.
- Preserve provider-reasoning materialization provenance across compact request
  conversion so source payload shaping removes only proxy-added aliases.
- Add regression coverage for both standalone compact routes and the equivalent
  terminal-trigger route controls.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-source-routing`: source compaction usage validation and reasoning
  alias provenance.

## Impact

Only compact collection, request policy/request models, and their integration
regressions change. No settings, migrations, credentials, deployment, commit,
or changelog updates are included.
