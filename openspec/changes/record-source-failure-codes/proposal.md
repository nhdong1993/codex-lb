## Why

On 2026-10-20 two Codex threads kept failing on the `ch-relay` model source. One showed `502 Model source failed the response`; the other showed `Compaction interrupted / Incomplete response returned, reason: upstream_eof`. The source sent a 169-byte failure frame each time, but every request-log row kept only codex-lb's own generic code, `model_source_response_failed`, and `upstream_error_code` was empty. Operators could not tell what the source reported without capturing packets on the production host.

The WebSocket sanitization stays as it is: provider messages may contain secrets or URLs, so clients must not see them. The source's own error **code**, however, is a short identifier and is safe to keep for triage.

## What Changes

- When a source-routed Responses attempt observes a source failure terminal (`error`, a typeless error record, or `response.failed`) and its row is not `success`, the request log stores the source's error code in the existing `upstream_error_code` column.
- The code comes from the failure's error object `code`, falling back to its `type`. An `error` frame without an `error` object uses its top-level `code`, falling back to its top-level `error_type`, the same fields the WebSocket error normalizer reads.
- The stored value is trimmed and lowercased. It must match `^[a-z0-9][a-z0-9_.:-]{0,63}$`; any other value is stored as `null`.
- The first failure terminal that carries a valid code wins. This covers a relay that sends `error` and then `response.incomplete`.
- No source error message is stored or logged. Client envelopes, `error_code`, `error_message`, status, settlement and account health are unchanged.
- No schema, migration, setting, API or frontend change. Telemetry already folds codes outside its safe set into `other`.

## Capabilities

### Modified Capabilities

- `proxy-runtime-observability`: add "Source failure terminals record the upstream error code" and "Source failure codes are sanitized identifiers".

## Impact

- `app/modules/model_sources/forwarding.py`: a `SourceUsageHolder.terminal_error_code` field, set by the Responses stream parser on its first failure terminal.
- `app/modules/proxy/source_dispatch.py`: `write_row()` passes that code as `upstream_error_code` for non-success rows.
- Applies to every source Responses stream that uses the shared parser: HTTP SSE, the native source WebSocket session and the WebSocket→HTTP bridge.

## Non-goals

- Exposing source messages to clients or storing them anywhere.
- Codes for source HTTP errors that arrive before the stream (those keep their current envelope handling).
- Chat-completions, embeddings and audio routes.
