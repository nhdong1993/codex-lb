# Verification

All runs were on the production Docker host, so test processes ran one at a time with `-n` ≤ 2. Times are UTC.

## Plan review

- `review-plan` sessions 001 and 002 returned REVISE with eight findings in total: warmup identity binding, warmup discard on every exit, the non-streaming pool error, contradictory warmup accounting, real-client evidence on both legs, workflow gates, the exhausted-failover error, and HTTP-open deadline classification. All eight were fixed in the plan.
- Session 003 returned APPROVE on 2026-10-18. Sessions 001 and 002 each ended at their second turn with a reviewer-host remote-compaction error, which is unrelated to this change.

## Implementation review

`review-impl` session 001 returned APPROVE in round 3 on 2026-10-18. Findings fixed along the way:

1. The continuation size check now covers the whole HTTP-equivalent resend, not only its input. It started as transcript + delta + other fields; round 2 made it exact (`_resend_size`). The exact formula was checked against `json.dumps` on 3000 random cases. `test_bridge_transcript_is_bounded[input|instructions]` and `test_bridge_resend_limit_boundary[0|1]` cover it: a request exactly at the limit is dispatched, and one byte over is rejected.
2. Concurrent HTTP closers share one close task (`_http_close_task`), so no path can finish a turn and return its admission while the response is still open. Covered by `tests/unit/test_source_websocket_bridge.py`.
3. The context rollout guidance now scopes the native flag. Disabling it switches the source to the bridge; the global `http` transport refuses client WebSocket handshakes.

## Automated tests

Each file ran by itself, mostly with `-n 2`, between 17:00 and 19:45 UTC on 2026-10-18:

| Suite | Result |
|---|---|
| `tests/integration/test_model_source_websocket_http_bridge.py` (new) | 18 tests; all pass when run alone. Under parallel runs during heavy host I/O (about 40% iowait), some first-turn receives exceeded the 5s client timeout. |
| `tests/unit/test_source_websocket_bridge.py` (new) | 1 passed |
| `tests/unit/test_source_dispatch.py` (new `discard()` test) | 125 passed |
| `tests/integration/test_model_source_websocket.py`, `test_source_http_only_handshake.py` | pass after the expectation updates below. Two native timing tests failed once under host load (load average ~10). Rerun alone, `test_source_websocket_retry_only_handshake_failure` passed 6/6 twice and `test_source_websocket_first_frame_deadline_restarts_per_turn` passed. |
| `test_model_source_websocket_input_discovery.py` | discovery and installer tests pass after the updates below. One 16 MiB native byte-limit case timed out once under load. |
| `test_model_source_websocket_policy_review.py`, `tests/unit/test_proxy_websocket_model_source_guard.py`, `test_model_source_websocket_transport.py`, `test_websocket_transport_fallback.py` | passed |
| `test_key_dashboard_install_catalog.py`, `test_v1_models.py`, `test_model_sources_catalog.py`, `test_key_dashboard_install.py` | 87 + unit passed after the updates below |
| `test_model_source_websocket_review.py` | 43 passed, 2 failed under load. Rerun alone, `test_source_retry_preparation_deadline` passed. `test_source_dashboard_timeouts_apply_to_source_session` also fails on the unchanged base commit `4075adcd`, so it is pre-existing. |
| `test_model_source_websocket_lifecycle_review.py` | 40 passed, 2 failed under load; both passed when rerun alone |
| `test_model_source_websocket_error_contract.py` | 44 passed. The 16 `test_unavailable_source_owner_preserves_http_error_envelope` failures also occur on base `4075adcd`: the disabled source empties the source-only pool, so the handshake returns 426. They are pre-existing. |
| `test_model_source_websocket_keepalive.py`, `test_model_source_fast_mode.py`, `test_model_source_subagent_blocking.py`, `test_model_source_websocket_migration.py` | 16, 6, 16 and 1 passed |

Expectation updates follow the new contract:

- HTTP-only streaming sources now prefer WebSocket in catalogs and enable the source-only installer flag. The handshake accepts them.
- Tests that relied on HTTP-only meaning "no WebSocket" now use non-streaming sources, which keep `model_source_requires_http_transport` after upgrade and 426 for source-only handshakes.

`ruff check`, `ruff format --check` and `ty check` (project venv) pass on the touched files. `npx -y @fission-ai/openspec@1.11.0 validate bridge-source-websocket-over-http --strict` passes.

## Real-client acceptance

Run on 2026-10-18 at about 19:45 UTC. The setup was codex-cli 0.163.0, an isolated `CODEX_HOME`, and an installer-shaped config (`supports_websockets = true`, base URL `/backend-api/codex`, `model_catalog_json` from `/api/key-dashboard/models`). Requests went through a logging relay to an isolated dev instance of this worktree (`app` imported from the worktree, SQLite) and then to a local HTTP/SSE stub source. The stub has no WebSocket endpoint and `supportsResponsesWebsocket=false`. It returns a `function_call` (unknown tool `codex_lb_bridge_probe`) first and a final message after the tool output. The harness is in the session scratchpad and is not committed.

Client leg (relay):

- One upgrade: `/backend-api/codex/responses` → 101. There were no client HTTP requests at all, so no fallback `POST …/responses`.
- Frames:
  1. `generate:false`, `input: []`. The proxy answered `response.completed` with `resp_b034e187…` and made no source request.
  2. `previous_response_id = resp_b034e187…`, input `[developer, user, user]` messages. Completed as `resp_src1`.
  3. `previous_response_id = resp_src1`, input `[function_call_output]`. Completed as `resp_src2`.
- `codex exec` exited with code 0 and printed `bridge ok`.

Source leg (stub POST bodies):

- Two POSTs. Each had `stream: true`, `store: false` and no `type`, `generate` or `previous_response_id`.
- Body 1 input: `[user env, user prompt]`. The developer message was hoisted into `instructions` by the existing request normalizer, as on HTTP.
- Body 2 input: body 1's input, then `function_call fc_probe1/call_probe1`, then `function_call_output call_probe1`.
- Every field except `input` (instructions, tools, prompt_cache_key and the rest) was identical across the two bodies, so the upstream prompt-cache prefix stays stable.

Dev request logs: two rows, `transport=websocket`, `upstream_transport=openai_compatible_http`, `status=success`, and no row for the warmup. The catalog showed `prefer_websockets: true` for the model and the installer had `supports_websockets = true`.

Not verified here: a real provider (ch-relay) and a production deploy. Both need operator approval.
