# Verification: deny-http-only-source-websocket-upgrades

Local verification and narrowly scoped operator configuration on 2026-10-12. No application deployment, commit or push.

## Summary

| Dimension | Result |
| --- | --- |
| Completeness | Handshake guard, route regression coverage and main-spec/context sync implemented |
| Correctness | One added requirement maps to the shared transport guard and effective installer capability helper |
| Coherence | Reuses source policy and the existing 426 envelope; no global WebSocket disablement or accepted-turn conversion |

## Evidence and coverage

- `app/modules/proxy/api.py::_websocket_upstream_transport_denial`: source-only keys reuse `source_only_key_supports_websockets`; incapable/empty pools deny before upgrade, and lookup exceptions return sanitized 503. Cancellation is not caught by the `Exception` handler. Mixed/unrestricted keys retain the existing path.
- Both Responses route functions still authenticate and apply firewall policy before this guard. Their existing required-capability exception remains unchanged and bypasses ordinary transport denial.
- `tests/integration/test_source_http_only_handshake.py`: four canonical/trailing-slash route variants reject with 426 before reservation/upstream I/O and still allow HTTP; capable-only and mixed keys accept; four lookup-error cases return sanitized 503; invalid authentication precedes capability lookup. Its ASGI helper owns and awaits/cancels its task on every exit.
- `tests/integration/test_model_source_websocket.py`: mixed-key in-band refusal retains its previous error contract; source-only rejection is now verified at handshake instead.
- `tests/integration/test_model_source_websocket_input_discovery.py`: installer, catalog and handshake agree for effective aliases, enforced models, fast-mode prohibition and aggregate eligibility. A source-only pool containing an eligible HTTP-only/nonstreaming model denies the handshake even when another selectable model supports WebSocket.

Completed checks (overlapping runs are not unique test totals):

| Check | Result | Local evidence |
| --- | --- | --- |
| New HTTP-only handshake suite | 11 passed | `/tmp/codex-source-http-only-tests.log` |
| Combined final upstream/HTTP-only suite, including mixed-key regression | 84 passed | `/tmp/codex-upstream-http-verified.log` |
| Complete effective-input/discovery and installer/catalog suites | 73 passed | `/tmp/codex-http-discovery-verified.log` |
| Existing global transport/marker handshake guards | 3 passed, 48 deselected | `/tmp/codex-http-transport-guard.log` |
| Ruff lint/format across eight touched Python files | Passed | Local CLI output |
| `ty check` across three changed production files | Passed | `/tmp/codex-upstream-typecheck.log` |
| Strict main-spec validation | 67/67 valid | `/tmp/codex-upstream-specs-current.json` |
| Strict change validation | Valid | `/tmp/codex-http-only-change-validation.json` |

The added requirement block matches the main spec. Operational context documents the source flag, provider-level setting, model-less handshake limitation and session-scoped client fallback.

## Production configuration and client evidence

- Incident logs showed 13 ch-relay WebSocket handshake 404s, matching gateway GET requests to `/v1/responses`. The operator confirmed that provider supports HTTP only.
- Updated exactly `ch-relay (VPS)` through `ModelSourcesService.update_source` with `supports_responses_websocket=False`, and recorded an audit event. HTTP support, models and credentials were not changed. Subsequent reads from blue, green and amber all reported HTTP enabled and WebSocket disabled. Both `ch-relay/gpt-6-astra` and `ch-relay/gpt-6.1-sol` consequently advertise false through the existing catalog helper.
- The key behind those failures was unrestricted, not source-only. The server cannot know its later model frame at handshake time. Disabling the source flag prevents native source WS attempts, but does not itself guarantee that an already configured mixed/unrestricted client falls back.
- The official [Codex client implementation](https://github.com/openai/codex/blob/main/codex-rs/core/src/client.rs), checked on 2026-10-12, uses provider `supports_websockets` and recognizes HTTP 426 during handshake for session-scoped HTTP fallback. Per-model catalog preference is not a substitute for that provider setting in the inspected client. Arbitrary client versions require separate verification.
- This host already has a separate HTTP profile, `codex-lb-custom`, whose provider uses `wire_api="responses"` and `supports_websockets=false`. It can be selected with `codex -p codex-lb-custom -m ch-relay/gpt-6-astra`. That profile is local to this host; other clients need their own equivalent provider configuration or a regenerated source-only installer.

## Limits

- New server handshake behavior is only in the working tree and needs a separately authorized deployment. Existing exported installers and active client sessions are not rewritten.
- Earlier broad source runs stopped on old accept/in-band expectations, which were updated for the new source-only handshake contract. Do not count those partial runs as full-suite success.
- No live paid generation, cloud merge gates or complete repository test suite was run. Existing unrelated working-tree edits were preserved.

Final strict main-spec validation again passed 67/67 (`/tmp/codex-upstream-specs-final.json`). No critical implementation or focused-scenario gaps found. Ready to archive with deployment/client limitations recorded.
