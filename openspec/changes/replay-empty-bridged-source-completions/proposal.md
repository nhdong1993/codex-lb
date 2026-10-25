## Why

On 2026-10-25 two consecutive Codex turns bridged to the `ch-relay` source (`ch-relay/gpt-6-astra`, served upstream as `gpt-6.1-sol`) ended with an empty answer. Codex showed only "…". Requests `resp_04a9e92aaeab08f0016add9de4148c8191a859e8c4f8a00bc4` (06:13:10 UTC) and `resp_04a9e92aaeab08f0016add9e2de5688191904714ddb36604ff` (06:14:30 UTC).

- **What the client got.** A normal stream: `response.created`, two reasoning items, an assistant `message` whose only text is `""`, then `response.completed` with `output_tokens` 1–2. No error and no truncation. Codex treats that as a finished turn and stops.
- **Fault boundary.** The source itself sent that stream. ch-relay logged `200 … in=90295 cached=0 out=1` and `in=90498 … out=2`. The request just before each one in the same turn reached upstream with about 113k input tokens. codex-lb forwarded the full reconstructed history both times: ch-relay's share endpoint rejects `previous_response_id` with `400`, and no `400` occurred. The roughly 23k missing tokens are lost inside ch-relay's own request rewriting, which logs nothing. The vendor binary (1.1.84) is a mandatory update, so a relay rollback is not available.
- **Rate.** 3 of about 2,000 Codex responses through this source since 2026-10-23 17:00 UTC, all after the 1.1.84 update. Each costs the user a manual re-prompt.

## What Changes

- **Hold output-free events too.** The first attempt of a bridged turn already holds back its lifecycle prefix. It now also holds back events that carry nothing visible, until the first visible output arrives:
  - reasoning items and reasoning summary or text events;
  - an assistant `message` and its content parts while all of its text is empty.

  Visible output is any other event: non-empty text or refusal, any non-reasoning, non-message output item, tool-argument deltas, failures and errors. When visible output arrives, the held events are published and delivered first, in order, and the attempt is no longer replayable.
- **Replay one empty completion.** If `response.completed` arrives while everything is still held back, and its `response.output` has nothing visible either, the attempt has answered nothing. It is finalized as a `success` that settles its reported usage. Its row is marked `error_code = model_source_empty_completion`. Nothing of it is published to source ownership or delivered. The turn is then re-sent once through the existing bridged replay path: same source, same revision, same model, same body, original deadline.
- **Usage counts.** The empty attempt's tokens are charged to the key and appear in the request log, the dashboards and log-based API-key limits, because the upstream really spent them.
- **Existing replay reach grows.** A reset, an EOF without a terminal, or a `server_is_overloaded` failure that arrives while reasoning is still held back is now also replayed. Before this change only a failure inside the lifecycle prefix was replayed.
- **No replay otherwise.** `response.incomplete` with only held events is delivered unchanged. A replacement is never replayed again. A replacement that also completes empty is delivered as it is. When the replacement cannot be prepared, the client gets a WebSocket `error` event `model_source_empty_completion`.
- No schema, migration, setting, API or frontend change.

## Capabilities

### Modified Capabilities

- `model-source-websocket`: "Bridged turns replay one pre-content source failure" holds output-free events and replays one empty completion.

## Impact

- `app/modules/proxy/source_websocket.py`:
  - a held-event classifier next to `_bridge_prefix_event`;
  - `_relay_http`, which holds, releases and detects the empty completion.

  `_bridged_replacement` and `_worker` stay unchanged: the existing replay path already logs the error code as `reason`.
- Tests: `tests/integration/test_model_source_websocket_http_bridge.py`.

## Non-goals

- Fixing ch-relay's context loss. That needs a vendor report, recorded in `context.md`.
- Native source WebSockets, the plain HTTP Responses route, and non-bridged clients.
- Replaying `response.incomplete`, or replaying after any visible output.
- Detecting answers that are short but not empty.
