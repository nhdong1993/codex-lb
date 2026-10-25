# Context: replay empty bridged source completions

## Incident (2026-10-25, Asia/Ho_Chi_Minh)

Session `01a16e89-3c80-7c71-b520-241f90bdd6d7`, Codex desktop over the WebSocket→HTTP bridge, model `ch-relay/gpt-6-astra`, source `src_a5a29b4a7a1e4620a233c6b43e424bd1` (ch-relay 1.1.84, upstream model `gpt-6.1-sol`).

| Request (UTC) | Input tokens | Output tokens | Client saw |
|---|---:|---:|---|
| 06:12:25 | 114,591 | 68 | tool call |
| 06:12:46 | 113,398 | 150 | tool call (`response.created` id ≠ `response.completed` id) |
| 06:13:10 | **90,295** | **1** | reasoning ×2, `message` with `""`, `completed` |
| 06:14:01 | 113,666 | 92 | tool call (`created` id ≠ `completed` id) |
| 06:14:30 | **90,498** | **2** | reasoning ×2, `message` with `""`, `completed` |

- **The stream was complete.** No reset happened. Codex recorded `task_complete` with an empty final message.
- **Correlation.** Since 2026-10-23 17:00 UTC, there were 74 responses whose `created` id differed from their `completed` id. 3 of the requests that followed one of them completed empty. Among 1,980 requests that followed a response with matching ids, none did. All 3 empty completions happened after the relay moved to 1.1.84 (2026-10-25 04:15 UTC).
- **Where the tokens went.** codex-lb always sends the full history. The relay's share endpoint answers `previous_response_id` with `400`. About 23k tokens, roughly the size of Codex's instructions plus tool definitions, are missing upstream. ch-relay rewrites requests internally: it trims old outputs, strips reasoning, splices autocut segments and retries with fallback bodies. It also discards every `share …` info log line, even at `CH_LOG=debug`, so the exact step could not be identified.
- **Why codex-lb.** The relay is a mandatory-update vendor binary and cannot be fixed or rolled back here. codex-lb can detect the empty answer before the client sees it, and it already owns a single same-source replay for pre-content failures.

## Decisions

- **What counts as output-free.** These events are held back:
  - the existing lifecycle prefix;
  - `response.output_item.added` and `response.output_item.done` whose item `type` is `reasoning`;
  - any `response.reasoning_summary_part.*`, `response.reasoning_summary_text.*` or `response.reasoning_text.*` event;
  - assistant `message` scaffolding while all of its text is empty after trimming whitespace: `response.output_item.added` and `response.output_item.done` of a `message` with no non-empty `output_text` text or `refusal`, `response.content_part.added` and `response.content_part.done` with empty text, and `response.output_text.delta`, `response.output_text.done`, `response.refusal.delta` and `response.refusal.done` with empty text.

  Any other event is visible, including unknown event types. Unknown types fail safe: they release the held events.
- **Only `response.completed` is an empty completion.** `response.incomplete` usually means a token limit was hit while reasoning, and a replay would repeat it, so it is delivered unchanged.
- **The completed envelope is checked too.** A source may send only `response.created` and a `response.completed` whose `response.output` carries the whole answer, with no output-item events. That is not empty. The envelope's output must also hold nothing but reasoning items and messages without non-empty text or refusal. Without this check, every turn on such a source would be paid and sent twice.
- **The empty attempt is a billed success.** It is finalized before the replay with `finish(status="success", error_code="model_source_empty_completion", trial_result="inconclusive")`:
  - Its reported usage settles the reservation. A limited key without reported usage settles the existing estimate, as any success does.
  - Its row is `status=success`, so dashboards and log-based API-key limits (`RequestLog.status == "success"`) count its tokens. `error_code` marks it, and `failure_detail` stays empty because success rows never carry the trace.
  - The trial result is `inconclusive`: the source answered, so it is neither rewarded nor put into cooldown.
- **Nothing of the empty attempt is visible.** Held events are not published to source ownership. Its response id is not remembered as a continuable transcript. The client sees only the replacement's events, with one `response.created` and one response id.
- **Replay path and bounds are unchanged.** The replay goes through `_bridged_replacement`, so it gets the same body check, the same source binding, a fresh admission and reservation, the original deadline and at most one replay per turn. The `source_bridge_replay` log line carries `reason=model_source_empty_completion`.
- **When the replacement cannot be prepared,** the client receives the WebSocket error `model_source_empty_completion` with status 502. Codex retries the turn on its own. The withheld empty answer is never delivered: it would end the turn silently, which is exactly what this change removes.
- **The 2 MiB withheld bound still applies.** Encrypted reasoning counts toward it. Past the bound, the held events are delivered and the attempt is no longer replayable.

## Residual risk

- **The client hears nothing for longer.** While reasoning is held, the client receives no events. For one reasoning item that silence is about as long as today's gap between its `added` and `done`. A response with several reasoning items now shows one silence covering all of them. Codex's stream idle timeout (300 s by default) bounds the risk.
- **Reasoning summaries arrive late.** They reach the client only together with the first visible output. The incident source sends empty summaries.
- **An empty answer costs twice.** The empty attempt and the replay both spend upstream quota. That is about 0.15% of this source's turns.
- **The relay bug remains.** The replay may complete empty again, and that answer is delivered. The vendor report is the real fix.

## Example

Attempt 1 streams `response.created`, a reasoning item (`added`, `done`), a `message` added with `content: []`, `response.content_part.added` with `text: ""`, `response.output_text.done` with `text: ""`, the `message` done with `text: ""`, and `response.completed` with usage `11/5`.

- Row 1: `status=success`, `error_code=model_source_empty_completion`, `input_tokens=11`, `output_tokens=5`. Reservation finalized.
- Log line: `source_bridge_replay request_id=<row 1> … reason=model_source_empty_completion`.

Attempt 2 returns a `message` with text `done`.

- The client receives only attempt 2's events.
- Row 2: `status=success`, `error_code` null.

## Operations

- **Measure:** `select count(*) from request_logs where error_code = 'model_source_empty_completion'`, compared with rows whose next row is a success, and with the `source_bridge_replay … reason=model_source_empty_completion` log lines.
- **Vendor report:** ch-relay 1.1.84 sends about 23k fewer input tokens upstream than codex-lb forwarded, for the request after a response whose `response.created` and `response.completed` ids differ. Evidence: the incident table above and the relay `usage` rows 58360–58363.
