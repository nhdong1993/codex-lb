# Verification — route-websocket-compaction-through-sources

Date: 2026-10-21. Local working tree on top of `2073de79d`. Integration tests use an isolated temporary SQLite database (`env -u CODEX_LB_TEST_DATABASE_URL`) and local HTTP/SSE and WebSocket stub sources. No production database or provider was used.

## Reproduction before the fix

`tests/integration/test_model_source_websocket_compaction.py` and the new policy-review test failed on the unfixed code, on both route families:

- first-turn bridged and native compaction reached the subscription path (the subscription fixture was called);
- a compaction on a bound bridged socket received 409 `websocket_reconnect_required`, the same error seen in production at 17:08:31 UTC;
- a disabled source and a subscription-anchored source-only compaction reached the subscription path instead of `model_source_disabled` / `model_source_requires_http_transport`.

`test_bridged_compaction_response_is_not_continuable` failed with `400 == 502` while the `_remember` change was disabled. That is the transcript replay defect from review round 1.

## Results after the fix

| Command | Result |
|---|---|
| `pytest tests/integration/test_model_source_websocket_compaction.py` plus the two policy-review tests | 14 passed |
| `pytest -n 2 tests/integration/test_model_source_routing.py test_model_source_dispatch.py test_model_source_aliases.py test_proxy_compact.py test_proxy_compact_triggers.py test_native_websocket_events.py test_model_source_compaction.py test_proxy_websocket_responses.py tests/unit/test_proxy_api_responses_contract.py` | 681 passed, 1 skipped |
| `pytest -n 2 tests/integration/test_model_source_websocket*.py tests/unit/test_proxy_websocket_model_source_guard.py tests/unit/test_request_policy.py tests/unit/test_source_dispatch.py` | 580 passed, 17 failed (see below) |
| `pytest -n 2 tests/integration/test_model_source_websocket_review.py` (rerun) | 45 passed |
| `ruff check`, `ruff format --check`, `ty check` on touched files | pass |
| `openspec validate route-websocket-compaction-through-sources --strict`; `openspec validate --specs` | valid; 67 passed |

Failures in the source WebSocket batch:

- `test_model_source_websocket_error_contract.py::test_unavailable_source_owner_preserves_http_error_envelope` (16 parameter combinations): **pre-existing**. The same 16 cases fail on a clean worktree of `2073de79d` without this change; the source-only key is refused with 426 at the handshake before any `response.create`.
- `test_model_source_websocket_review.py::test_source_dashboard_timeouts_apply_to_source_session` (1): **timing flake under load**. It uses a 0.25 s idle timeout with a 1.25 s wait on a native session without compaction, and the host load average was about 7 during the parallel run. It passed 5 of 5 isolated reruns and in a full rerun of its file.

## Review

`review-impl` session `review-impl-20261021-001`: round 1 REVISE with one plan-gap (continuation after a bridged compaction). The operator chose option A; it was fixed under tasks 2.6/3.3. Round 2 APPROVE.

## Pending

Production verification after deployment: a Codex auto-compaction on a `ch-relay/*` model must appear in request logs with `request_kind=compaction`, `transport=websocket` and a `model_source_id`.
