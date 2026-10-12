## Why

Two accounts repeatedly return OpenAI's processing-error message with code `server_error`, which currently bypasses the sustained-overload window. Intermittent successful requests reset the generic error counter and prevent reliable escalation.

## What Changes

- Count `server_error` only when its upstream message matches OpenAI's processing-error/help-center signature in the existing backoff and isolation window.
- Preserve existing overload codes, thresholds, replica-local state, settlement ordering, account ownership, and client error envelopes.
- Ensure terminal-stream health writes await confirmed API-key settlement, including startup-probe stream closure.
- Cover positive and negative messages and the failing public proxy routes with regression tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `account-routing`: Recognize message-qualified OpenAI server errors as additional evidence for sustained backoff and isolation.

## Impact

The shared stream error-health funnel and overload predicate change. No schema, setting, dependency, or deployment change is required.
