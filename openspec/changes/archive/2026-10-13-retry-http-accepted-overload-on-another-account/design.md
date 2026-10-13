## Context

See `proposal.md` (Why) for the production evidence. Current direct HTTP/SSE flow:

- `_StreamingRetryMixin._stream_with_retry` (`streaming/retry.py`) owns account selection, exclusion, the attempt loop (`_STREAM_MAX_ACCOUNT_ATTEMPTS = 3`), and pre-visible failover. Raising `_RetryableStreamError(..., exclude_account=True)` from an attempt already does the following:
  - writes the account's health, deferred behind API-key settlement (`_handle_or_defer_keyed_stream_health`)
  - releases the stream lease and excludes the account
  - continues to the next selection
  - if selection then fails, surfaces `last_retryable_stream_error.code` as `response.failed` instead of `no_accounts`
- `_stream_once` (`streaming/mixin.py`) reads the first upstream frame, yields it, then relays the rest.
  - A `response.failed` / `error` frame as the *first* event becomes `_RetryableStreamError` only for `_ACCOUNT_RECOVERY_RETRY_CODES` (quota, rate limit, permanent failures). Every other first-event terminal becomes `_TerminalStreamError`, which the loop treats as fail-closed.
  - A terminal after the first frame is forwarded in the relay loop and never reaches the retry machinery.
  - Each attempt writes its own request-log row in `finally`.
- `http_bridge/accepted_replay.py` already holds the output-free proof the bridge and WebSocket surfaces use: `_terminal_payload_reports_output`, the capacity code set, and the quota/rate-limit fail-closed set.
- `scripts/check_proxy_architecture.py` caps the line count of `streaming/mixin.py`. That file is at the ceiling, so new logic has to live in a helper module.

## Goals / Non-Goals

**Goals:**
- Turn an output-free capacity terminal on a movable direct SSE stream into the existing pre-visible `_RetryableStreamError` failover, with no frame of the failed attempt reaching the client.
- Keep the stream byte-for-byte unchanged for every turn that produces output, and for every stream that cannot move.

**Non-Goals:**
- Same-account replay for owner-bound streams. Overload is account-scoped, so a same-owner re-send mostly replays the rejection wait.
- Renumbering or id-rewriting a lifecycle the client has already seen. That is the bridge's mechanism and is not needed here.
- Compact (`/responses/compact`), non-Responses routes, and the HTTP bridge / WebSocket surfaces, which already have their own replay.
- Any change to overload backoff or isolation tuning.

## Decisions

### D1. Hold the prelude instead of rewriting a visible lifecycle

A movable stream holds `response.created` / `response.in_progress` / `response.queued`, plus any non-`response.*` frame that arrives first, until the first other event. On a capacity terminal the held frames are dropped, so the replacement attempt's own `response.created` is the first the client ever sees.

*Alternative considered: forward the prelude and rewrite the replay's ids, suppressing its duplicate prelude.* This is what the bridge does. On direct SSE it would mean rewriting `response.id` in every later frame and accepting a repeated `sequence_number`; the existing spec already lists that as a bridge limitation. Holding costs nothing on success: upstream sends nothing between `response.in_progress` and the first output item, so the client receives the same frames at most one upstream event later. Liveness during the hold is already covered by the SSE heartbeat requirement ("Public Responses streaming is proxy-timeout friendly"), and the API-layer startup probe commits headers after its existing timeout.

### D2. Eligibility is decided once per attempt in `retry.py` and passed down

`_stream_with_retry` passes a new `allow_capacity_replay` keyword to `_stream_once`. It is true only when all of the following hold:

- `allow_retry_flag` (an attempt remains)
- `not capacity_replay_used`
- `resilience.deterministic_failover_enabled`
- `not _stream_owner_bound_to(account)` (covers `single_account`, required preferred owner, file owner, turn-state owner, payload-bound owner)
- `payload.previous_response_id is None`
- remaining budget > 0

`_stream_once` never re-derives ownership, so the owner-crossing invariant has a single source.

*Alternative considered: compute eligibility inside `_stream_once`.* Rejected. It would duplicate the `can_try_other_account` predicates the loop already owns.

### D3. New helper module `streaming/capacity_replay.py`

- `CapacityReplayPrelude` wraps the upstream line iterator; `hold_capacity_replay_prelude(...)` returns it only when `allow_capacity_replay` is true and otherwise hands back the upstream iterator untouched. It buffers prelude lines (bounded at 8 frames; a longer prelude stops being held) until the first non-prelude line:
  - an output-free capacity terminal (`is_output_free_capacity_terminal`) drops the held prelude, sets `capacity_terminal`, and becomes the only frame handed out, so `_stream_once` sees it as a first-event failure;
  - any other line hands out the held frames in order, then that line, then passes everything through;
  - `StopAsyncIteration` or a transport exception while holding hands out the held frames first and re-raises afterwards, so the existing incomplete-stream handling is unchanged.
- The wrapper releases the response-create admission and account lease when the first upstream frame arrives (both releases are idempotent), so the hold never stretches response-create admission past the moment the unheld stream released it.
- `is_output_free_capacity_terminal` reuses `_ACCEPTED_CAPACITY_REPLAY_ERROR_CODES`, `_ACCEPTED_REPLAY_FAIL_CLOSED_ERROR_CODES`, `_terminal_payload_reports_output` and `is_upstream_model_capacity_error` from `http_bridge/accepted_replay.py`, and only accepts frames that parse as lifecycle events, which keeps it in agreement with the branch of `_stream_once` that acts on the flag.
- `_stream_once` keeps its existing first-event classification (status, error code, settlement fields for the failed attempt's request log) and, in the non-rewritten branch, calls `raise_if_capacity_replay(iterator, code, upstream_error)`, which raises `_RetryableStreamError(code, error, exclude_account=True, capacity_replay=True)` only when the wrapper flagged the frame. The wrapper is the single decision point.
- To stay under the `streaming/mixin.py` line ceiling, the two identical-shape `except` blocks around the first `__anext__()` (`StopAsyncIteration` and `aiohttp.ClientError`/`asyncio.TimeoutError`) were merged into one, with the error code and message chosen by exception type.

*Alternative considered: classify inside the relay loop of `_stream_once`.* Rejected. The relay loop has already yielded the prelude by then, and the mixin cannot grow.

### D4. One replay per request, tracked in the loop

`_stream_with_retry` sets `capacity_replay_used = True` when it catches a `_RetryableStreamError` that came from `CapacityReplayRequested`. Implementation: the `capacity_replay` keyword on `_RetryableStreamError`, so the loop does not have to match on codes. The replacement attempt therefore runs with `allow_capacity_replay=False`: no hold, and its capacity terminal is forwarded unchanged. If the next selection finds no account, the existing `last_retryable_stream_error` branch surfaces the capacity code. Its `no_accounts` path is never reached for this case.

### D5. Health and logging reuse the existing failover path

The `_RetryableStreamError` handler already writes the health and defers it behind keyed settlement, so overload backoff sees the rejection exactly as it sees a WebSocket one. The failed attempt's request-log row keeps `server_is_overloaded` and its account. One `logger.info("http_capacity_replay ...")` line with request id, account id, code, and held-frame count gives operators a grep target. This mirrors the bridge's `Accepted output-free replay staged` log.

## Risks / Trade-offs

- [Risk] A turn whose first output arrives long after `response.in_progress` shows `response.created` to the client later than before. → Mitigation: the heartbeat already keeps the connection alive. Only movable streams hold. TTFT is measured from the first output event, so it is unaffected.
- [Risk] Excluding the overloaded account in a Plus pool where most accounts are overloaded may land on another overloaded account. → Mitigation: upstream rejections are independent per admission (~20 % peak). One replay cuts surfaced overloads to roughly 4 % without amplifying load beyond one extra admission. Overload backoff keeps steering fresh selection away from tripped accounts.
- [Risk] Reversing the "serialized capacity event surfaces without replay" boundary could re-POST a turn that had side effects. → Mitigation: the re-POST requires the same output-free proof the bridge and WebSocket surfaces already rely on (no output items, no billed output or reasoning tokens, no model-output event observed). Quota/rate-limit codes, `server_error`, and transport failures keep fail-closed handling.
- [Trade-off] Request logs now show two rows (overloaded attempt plus replacement) for a request the client saw succeed. This is intentional, because it keeps the overload rate observable, and it matches existing pre-visible failover logging.

## Migration Plan

No data or configuration migration. Roll out through the normal HA surge deploy. To roll back, revert the change. The behavior is gated on the existing `deterministic_failover_enabled` resilience toggle, which an operator can turn off from the dashboard to restore the old surfacing without a deploy.

After deploy, verify:

- `http_capacity_replay` log lines appear during peak hours.
- Over the next peak window, the client-visible overload rate drops: count `request_logs` rows with `transport='http'` and `error_code='server_is_overloaded'` that have no successful sibling row for the same `request_id`.
