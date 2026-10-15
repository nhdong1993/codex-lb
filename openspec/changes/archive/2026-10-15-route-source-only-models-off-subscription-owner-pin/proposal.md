## Why

On 2026-10-15, Codex Desktop requests on the direct Responses WebSocket failed with a terminal 400. Each one asked for a model that only an OpenAI-compatible model source serves. The client first sent a `generate:false` warmup for a subscription model on a ChatGPT account. It then chained the source-model turn to that warmup with `previous_response_id` on the same socket. Request logs recorded the account as the owner of that response, and the current "Previous-response source routing follows proven ownership" rule keeps a recorded subscription owner on the owner-bound subscription path. Both WebSocket source guards are skipped when an owner is recorded. The turn therefore reached a ChatGPT account, which answered `invalid_request_error` "The 'http/gpt-6-astra' model is not supported when using Codex with a ChatGPT account." Nothing retried it: the `account_model_unsupported` replay cannot move an anchored turn, every ChatGPT account rejects the slug, and Codex treats 4xx as terminal.

An unscoped API key never source-routes a subscription-registry slug. So a source-routed model that has no registry candidate cannot be served by a subscription account, and for such a model the owner veto always ends in a terminal 400.

## What Changes

- Define a *source-only* model: a model that an enabled or disabled Responses-capable source claims under the ordinary selection rules, where no model candidate (the raw client model, or the API key's enforced model when one is set, and the normalized model) is in the subscription model registry.
- On the direct Responses WebSocket transport, recorded subscription continuity (the `previous_response_id` owner or a turn-state owner) no longer sends a source-only turn to a subscription account. This includes sockets that an earlier warmup bound to a subscription account. The turn gets the service-level 503 `model_source_requires_http_transport` instead, so Codex falls back to HTTP. It is not forwarded to the source over WebSocket.
- Side effects of checking the turn-state owner branch too, for source-only models:
  - On a socket bound to a native source session, a subscription-anchored turn now gets that 503 instead of 409 `websocket_reconnect_required`.
  - On a reused subscription socket, a turn-state-only anchor now gets the in-band 503 instead of a terminal `response.failed`.
  - A first turn with only a turn-state anchor still gets 503, but no request-log row is written now.
- If any candidate is a registry slug, the current owner precedence stays. This includes source-scoped keys that route a registry model to a source.
- Structural subscription exclusions (terminal `compaction_trigger`, `input_file` references) and required-capability routing still take precedence. HTTP behavior does not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `responses-api-compat`: Narrow the WebSocket recorded-owner precedence in "Previous-response source routing follows proven ownership" for source-only models, and align the precedence sentence in "A disabled model source refuses its models instead of falling through".
- `model-source-websocket`: Clarify that subscription-owned anchors keep their precedence over source dispatch but do not route a source-only model to a subscription account.

## Impact

- Backend: a shared predicate `responses_model_is_source_only` in `app/modules/model_sources/selection.py`. It is used in both owner branches (turn-state owner and previous-response owner) of `_prepare_source_websocket_turn` in `app/modules/proxy/api.py`, before admission, reservation and request-log preparation. The WebSocket connect and reuse source guards in `app/modules/proxy/_service/websocket/mixin.py` are unchanged. They were verified to be reachable for a source-only model only through sanctioned precedence (capability routing, structural exclusions).
- Tests: regressions on the public WebSocket route covering:
  - the warmup-then-source-turn incident shape and a first-turn recorded owner;
  - a turn-state owner;
  - a source-bound socket;
  - registry-slug precedence;
  - a disabled source;
  - structural exclusion.

  Existing HTTP owner-veto tests must pass unchanged.
- No schema, migration, setting, dashboard or public envelope changes. `model_source_requires_http_transport` is an existing error code.

## Non-goals

- Changing HTTP Responses routing, including the HTTP owner veto for source-only models (recorded in `context.md` as a known gap).
- Translating a WebSocket turn to HTTP inside the proxy, or forwarding a subscription-anchored turn to a source.
- Changing handshake-time transport policy (`Source-only handshakes honor effective HTTP-only capability`).
