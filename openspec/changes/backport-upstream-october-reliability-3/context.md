## Scope and rationale

Round 3 of the selective upstream backport. The sources are upstream commits from `origin/main` (`72630bbf`):

| Area | Upstream | Fork commit purpose |
| --- | --- | --- |
| Proxy | `6b3d031e` (#2248) | retire a denied proxy-injected WebSocket anchor |
| Proxy | `09b8e891` (#2315) | one shared lock-wait deadline for the detached-bridge sweep |
| Proxy | `976d20b7` (#2357) | anonymous output frames go to the single created response |
| Clients | `bb98cdf4` (#2110) | cached system-trust TLS context for Python WSS |
| Clients | `ff6f6a17` (#2113) | skip unused preparation serialization |
| Warm-up | `a7785a80` (#2205) | one initial warm-up for fully unused Free quota |
| Dashboard | `a408b57a` (#2235) | index-bounded conversation raw tail |
| Dashboard | `913c6eb5` (#2236) | 60 s trailing-demand memo |
| UI | `0f6a31c5` (#2060) | Resume for `deactivated` accounts |
| UI | `ec994599` (#2489) | faithful quota chart, per-account panel state |
| Planner | `a3aa8caa` (#2468), `6ed4c44f` (#2540) | timezone and clock-time validation |
| Routing | `6cdf29ef` (#2233) | background state builds follow the dashboard snapshot |

**Deferred**, each with its own reason:
- `b04b2781` (#2387) and `63314a1b` (#2384): HTTP-bridge only.
- `ffaf6878` (#2247) with `cb21daae` (#2386): transport-policy change.
- `10cd71ad` (#2390) with `2852cf60` (#2397): migration.
- `44c635b9` (#2246): index builds during surge.
- `3d90273e` (#1997): durable spool ordering and a migration.
- `92c7f620` (#2320): changes the default probe model.
- `0da41b64`: automation migration.
- The dependency bumps.

**Skipped:**
- `dda902de` (#2258): no effect at fleet scale.
- `ef701057` (#2367): HA blocker.
- `5be82ef4`: already present.
- `905f647b`: package not locked.
- `68dfc0e0`: dialogs rewritten in the fork.

## Constraints and preservation

The following fork behaviors must survive:

- **Native Codex HTTP routing:** it stays out of the HTTP bridge unless the operator sets the upstream transport explicitly to `websocket` (`app/modules/proxy/_service/streaming/retry.py:225-228`).
- **Round-2 any-window reset recovery** (`reset_evidence`).
- **WebSocket payload budget:** sized from `settings.max_sse_event_bytes`.
- **Warm-up features:** new-account warm-up (`202fbd31`), the dashboard warm-up settings, staggered idle warm-up.
- **Capacity replay** and early same-replica owner publication.
- **Model-source routing** ahead of account admission, the source WebSocket, and the WS→HTTP bridge.
- **Proxy architecture ratchets:** `load_balancer_lines` 3021, `streaming_mixin_lines` 1100.

## Failure examples (before this change)

- **#2248:**
  - A Codex WebSocket thread sends an incremental turn `[user, function_call_output call_1]`.
  - The proxy injects `previous_response_id=resp_1`, upstream answers `previous_response_not_found`, and the turn fails closed.
  - The next turn is re-anchored to `resp_1` again and fails the same way.
- **#2315:** three detached bridge sessions hold their locks. The finalization sweep waits 5 s on each, 15 s in total, before the response finishes.
- **#2357:**
  - Request A has received `response.created`; request B is still waiting for its own.
  - An anonymous `response.output_text.delta` is matched to B, so A's output is truncated.
- **#2110:** every upstream `wss://` connect builds a fresh `ssl.create_default_context()`, repeating certificate-store loading.
- **#2113:** a 1 MB Responses request on Python HTTP without tracing is serialized twice before the real request body is built.
- **#2205:** a Free account imported with warm-up enabled reports 0% monthly use forever. Its monthly `reset_at` slides with every sample, so no reset is ever confirmed and no warm-up is sent.
- **#2235:** a 7-day conversation count scans every `request_logs` row in the window and filters per row. Upstream measured 401k rows in 322 ms on 800k rows, against 9.5k rows in 31 ms with index ranges.
- **#2236:** every dashboard overview and projections poll re-runs a 7-day `LAG` window over `usage_history`.
- **#2060:** an account deactivated by `deactivated_workspace` shows only Re-authenticate, although the reactivate endpoint accepts it.
- **#2489:** a primary series missing a sample at a secondary timestamp is drawn as 0%.
- **#2468:** `PUT /api/quota-planner` with `timezone: "Mars/Base"` is stored, and a stored `"../x"` makes the forecast raise `ValueError`.
- **#2540:** `PUT /api/quota-planner` with `workingHoursStart: "25:00"` is stored. It is now rejected with 422.
- **#2233:** an operator turns soft drain off in the dashboard, but usage-refresh recovery still builds the account's state with the environment default (on).

## Operations

**After deploying this change, watch for 24 h** (read-only):
- Warm-up attempts by status (`succeeded`, `failed`, `skipped`, `pending`). Expect roughly 1,800 attempts during the first refresh cycle (an estimated 3–4 h), then a return to the previous rate.
  - Signal: a sustained failure rate clearly above the ~2% baseline.
- Upstream 429s and request latency.
- Monthly-window freshness and refresh-cycle progress (distinct accounts with a monthly sample per hour).

**Fallback:** revert the #2205 commit and redeploy. This stops future initial warm-ups. It does not undo warm-ups already sent, and no data cleanup is needed.

The initial warm-ups start monthly windows for many Free accounts within a few hours, so their monthly resets may cluster about a month later. Confirm this from later monthly samples; do not assume it.
