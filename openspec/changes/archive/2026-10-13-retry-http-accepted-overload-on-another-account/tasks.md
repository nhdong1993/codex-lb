# Tasks

## 1. Reproduction

- [x] 1.1 Add direct SSE integration tests in `tests/integration/test_proxy_transient_retry.py` with two accounts, where account A emits `response.created` + `response.in_progress` + `response.failed` (`server_is_overloaded`, then `model_at_capacity`, no output) and B succeeds. Assert one POST to each account, exactly one `response.created` (B's) downstream, B's `response.completed`, and A excluded with a capacity health failure. Verify the tests fail on the current head.
- [x] 1.2 Add the first-event variant (capacity terminal with no preceding `response.created`). Rework `test_stream_overload_alias_surfaces_without_replay` so its single-account case asserts the capacity code surfaces (not `no_accounts`) after one POST. Verify the multi-account variant fails on the current head.

## 2. Helper Module

- [x] 2.1 Add `app/modules/proxy/_service/streaming/capacity_replay.py` with `output_free_capacity_code` (reusing the capacity code set, quota fail-closed set, `_terminal_payload_reports_output`, and `is_upstream_model_capacity_error` from `http_bridge/accepted_replay.py`), `CapacityReplayRequested`, and `hold_lifecycle_prelude`. Verify with unit tests in `tests/unit/test_streaming_capacity_replay.py` covering the following, each against a passthrough-when-disabled control:
  - flush order on the first output event
  - flush on a non-capacity terminal
  - flush-then-reraise on EOF and on a transport error during the hold
  - refusal for terminals reporting output, billed output tokens, or reasoning tokens
  - refusal for quota and rate-limit codes even with the capacity message
  - `model_at_capacity` reported as `server_is_overloaded`

## 3. Wiring

- [x] 3.1 In `streaming/retry.py`, compute `allow_capacity_replay` per attempt from `allow_retry_flag`, `capacity_replay_used`, `resilience.deterministic_failover_enabled`, `_stream_owner_bound_to(account)`, `payload.previous_response_id is None`, and remaining budget. Pass it to `_stream_once`. Set `capacity_replay_used` when the caught `_RetryableStreamError` carries the capacity-replay marker. Verify with the 1.1 and 1.2 tests and a test that a replacement capacity failure surfaces one terminal with no third POST.
- [x] 3.2 In `streaming/mixin.py`, wrap the native iterator with `hold_lifecycle_prelude` and map `CapacityReplayRequested` to failed-attempt request-log fields plus a marked `_RetryableStreamError(exclude_account=True)`. Emit the `http_capacity_replay` info log. Verify that `uv run python scripts/check_proxy_architecture.py` still passes (mixin line ceiling) and that the 1.x tests pass.

## 4. Invariant Coverage

- [x] 4.1 Add integration tests showing no hold and no replay for owner-bound streams (`_stream_owner_bound_to`, exercised with an account-bound payload on a native Codex route) and for the deterministic-failover toggle disabled. The capacity terminal must surface after exactly one POST. `single_account` and `previous_response_id` take the same predicate (`allow_capacity_replay` is false) and are not separately exercised here.
- [x] 4.2 Add integration tests showing no replay for these cases, with the prelude still delivered before the terminal:
  - output before the terminal (`response.output_item.added`, text delta)
  - a terminal reporting `usage.output_tokens > 0`
  - a `server_error` terminal
  - a `usage_limit_reached` terminal carrying the capacity message
  - the deterministic-failover toggle disabled
- [x] 4.3 Add an API-key-backed integration test asserting that A's capacity health write happens only after the request's reservation settlement, and that the reservation is settled exactly once across both attempts.
- [x] 4.4 Add a `/v1/responses` streaming test asserting the replayed stream still begins with `response.created`, carries exactly one `response.created` and no `codex.keepalive`. Add a non-streaming `/v1/responses` test asserting the collected result comes from account B.

## 5. Verification

- [x] 5.1 Run `uv run ruff check`, `uv run ruff format --check`, `uv run python scripts/check_proxy_architecture.py`, the touched streaming unit and integration suites, and `npx --yes @fission-ai/openspec@1.11.0 validate retry-http-accepted-overload-on-another-account --strict`. All must pass.
- [x] 5.2 Add the stable rationale (prelude hold vs lifecycle rewrite, output-free proof, one-replay budget) to `openspec/specs/responses-api-compat/context.md` and verify `openspec validate --specs` passes.
