Two remaining defects were reproduced in three /tmp test cases; 20 targeted existing regressions passed without timeout. Scoped production-file hashes remained unchanged. Verification used isolated SQLite and mocked upstream failures; live PostgreSQL, production, and the full suite were not exercised.

Full review comments:

- [P2] Catch admission errors during cold WebSocket selection — /home/dong01/codex-lb/app/modules/proxy/load_balancer.py:694-694
  On a cold WebSocket connection to either response route, a model-evidence connection failure becomes a 503 here, but `_select_websocket_connect_account` rethrows non-budget errors before the request-local handler. Reproduced with the real selector: both routes emit `stream_incomplete`, then propagate `ProxyResponseError` out of the socket handler, preventing same-socket retry. Handle normalized admission failures at the connect boundary, settling only the unsent turn. Cover both real routes rather than the mocked connector, consistent with [AGENTS.md:130–137](AGENTS.md#L130-L137).

- [P2] Fence evidence consumption for ordinary refreshes — /home/dong01/codex-lb/app/modules/usage/updater.py:711-713
  If an ordinary refresh persists Free, then credential replacement and a fresh Free observation occur before this clear, `_plan_check_generation` is `None` and the old worker deletes the replacement's evidence unconditionally. Reproduced through real persistence, scheduler and account-summary API: after two transient failures, the final attempt restarts confirmation at one observation and leaves `planType=plus` with `planCheckPending=false`. Fence ordinary evidence consumption against replacement too, or consume atomically with persistence; retain scheduler/API regression coverage per [AGENTS.md:130–133](AGENTS.md#L130-L133).
