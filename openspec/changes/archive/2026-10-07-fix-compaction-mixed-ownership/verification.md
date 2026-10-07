# Verification: fix-compaction-mixed-ownership

Local verification on 2026-10-07. No deployment, restart, commit or credential
change is included. The source-only routing and schema corrections from the
previous changes remain in place.

## Implementation review

All three HTTP handlers now perform source ownership validation before account
dispatch, including when subscription continuity or file pins suppressed source
selection. The existing helper queries scoped durable ownership, ownership
history and legacy source response logs. It returns 409 for known source state
and 502 if lookup fails. Disabled-source denial remains conditional so a
configured/disabled source alone cannot override subscription continuity.

Both standalone compact routes retain their compact schema until source
selection wins. The source dispatch, stream collection, settlement and cleanup
code is unchanged by this correction. The ordinary Responses turn-state rule is
also retained: that header alone does not suppress source selection, so a
source-owned ordinary continuation remains on its source.

## Focused evidence

`test_compact_state_never_crosses_to_subscription_owner` covers 36 combinations
of both standalone compact routes, both HTTP trigger routes and both ordinary
Responses continuation routes, with encrypted-only or item-reference state and
subscription previous-response, turn-state or file anchors. Source output is
created through a real local HTTP fixture; subscription ownership uses real
request logs, durable turn-state registration and file pins.

32 conflicting requests return 409 before source or subscription dispatch and
before another reservation. Four ordinary source continuations carrying a
turn-state header remain on the original source. Two lookup-failure cases return
502 without dispatch or a new reservation. Six existing subscription-only
positive cases preserve their compact extras and subscription route.

The focused selection (`crosses_to_subscription or mixed_compact_ownership_lookup
or respects_subscription_continuity`) passed **44 cases**. Initial expectations
for ordinary Responses with turn-state incorrectly assumed compact routing;
they were corrected to preserve the existing source continuation contract,
without changing application routing for that header.

## Checks

- Focused mixed-ownership and subscription preservation selection: **44 passed**.
- Source pool, source dispatch, request policy, replay portability and source
  forwarding regression suites: **393 passed**.
- Full compact/source compact/trigger/API-key integration suites: **341 passed**
  (`TMPDIR=/dev/shm uv run pytest -q tests/integration/test_model_source_compaction.py
  tests/integration/test_proxy_compact.py tests/integration/test_proxy_compact_triggers.py
  tests/integration/test_api_keys_api.py --timeout=45 --maxfail=3`).
- Ruff check, Ruff format check and `uv run ty check` on the two changed Python
  files: passed.
- Proxy timing seam and cancellation safety checks: passed.
- `git diff --check`: passed.
- Strict OpenSpec change validation: passed. After synchronization and archive,
  `openspec validate --specs --strict --no-interactive`: **67 passed, 0 failed**.

The two full suite runs cover **734 distinct passing tests**; the focused 44
are included in that count. Checks use synthetic local HTTP traffic and test
databases isolated per process. They do
not constitute production deployment validation. The initial working-tree
baseline and scoped patch were saved under `/tmp/compaction-mixed-owner-baseline`
and `/tmp/compaction-mixed-ownership.patch` to separate this fix from existing edits.
