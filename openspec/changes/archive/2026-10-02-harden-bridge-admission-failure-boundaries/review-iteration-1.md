Temporary SQLite product-path repros confirmed both remaining defects. Concurrent external edits fixed the earlier cold-bridge failure; findings reference the latest inspected code. PostgreSQL contention and the full suite were not verified.

Full review comments:

- [P1] Read the admission error payload as a mapping — /home/dong01/codex-lb/app/modules/proxy/_service/websocket/mixin.py:2549-2549
  When the first model-evidence lookup on a reused WebSocket fails, `exc.payload` is a dictionary, so `.error.message` raises `AttributeError`. Reproduced on both response routes: the socket disconnects, accepted sibling work is interrupted, and cleanup reaches an account-health write. Extract the message through `_parse_openai_error` or mapping access so rejection remains request-local, preserving the partial-failure lifecycle invariant in [AGENTS.md:116–120](AGENTS.md#L116-L120).

- [P2] Preserve confirmed downgrade evidence after a rotation conflict — /home/dong01/codex-lb/app/modules/usage/updater.py:923-925
  If routine OAuth rotation commits after the second Free observation is cleared but before metadata persistence, the refresh-token guard rejects the write and this branch discards the confirmation. With one earlier attempt consumed, the remaining attempt records only a new first observation and exhausts verification. A scheduler/API repro leaves `planType=plus` and `planCheckPending=false` despite agreeing Free samples and unchanged credential lineage. Preserve evidence until persistence succeeds, or retry against freshly loaded credentials after verifying that the same check generation remains current.
