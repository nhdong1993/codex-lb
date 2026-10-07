## Context

All three findings are confirmed through local HTTP fixtures on both compact
routes. Current ownership, admission and settlement logic is shared with source
Responses and should continue to own cleanup.

## Goals / Non-Goals

Correct the three reviewed failures while preserving existing subscription
compact extras, mixed ownership denials, streamed trigger behavior and large
terminal handling. Do not refactor unrelated routing, change WebSocket behavior,
add configuration or perform a rollout.

## Decisions

1. Pass `require_streaming=True` to initial compact selection and its disabled
   source probe. The adapter always sends streaming Responses, so model alias
   selection must use this capability before choosing a public model.
   After a streaming miss and its disabled-source probe, check whether a
   non-streaming source still claims the model. Such a capability miss must
   retain the former source-busy/disabled denial, never authorize subscription
   fallback. Do not run this availability guard for recorded subscription or
   file-owned requests. This addresses the re-review's enabled/disabled
   non-streaming-only counterexample.
2. The compact collector already parses complete bounded SSE events. Reuse the
   source Responses usage extractor there, keeping only the latest validated
   scalar counters. Preserve terminal response usage when present; otherwise
   construct the existing typed usage envelope from the observed counters.
   The resulting JSON is the common source of client usage and quota settlement.
   This also preserves large events beyond the lower-level observer's cap.
3. Catch only Pydantic validation errors around the reused terminal error
   translator and raise the existing `invalid_upstream_response` 502. Keep
   upstream status 200, so the source pool cannot replay an already-opened
   request. Do not catch cancellation or broad exceptions.

## Risks / Trade-offs

Observed usage must not replace malformed or negative terminal usage silently.
The collector retains only scalar counters, and terminal usage keeps precedence.
Streaming alias fallback must not bypass retained ownership. Tests cover these
interactions along with real HTTP error envelopes and finalization.

## Validation

Cover both standalone paths and their terminal-trigger counterparts. Check
public/upstream models, selected credential, disabled fallback, usage JSON,
token counters, reservation settlement, one attempt on malformed errors and
zero held admission. Reuse the prior review reproductions as an external check.
Run relevant compact/dispatch/routing suites, lint/type checks, strict OpenSpec
validation and an independent Codex CLI re-review before archive.
