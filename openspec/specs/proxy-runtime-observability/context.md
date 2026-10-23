# Proxy Runtime Observability Context

## Purpose and Scope

This capability defines what operators should be able to see in the live server console while debugging proxy traffic.

See `openspec/specs/proxy-runtime-observability/spec.md` for normative requirements.

## Decisions

- **Timestamps are always on:** timestamped console logs are a baseline operator need, not a debug-only feature.
- **Request tracing is opt-in:** outbound request summary and payload tracing remain configurable because payload logs can be noisy or sensitive. Since issue #1340 phase 1 the switch is the single `CODEX_LB_TRACE` comma-separated channel list (`shape`, `shape_raw_cache_key`, `payload`, `service_tier`, `upstream_summary`, `upstream_payload`); empty default = all off. It is an incident-debugging knob for interactive use only.
- **Error logs must be correlated:** request id, endpoint, status, code, and message are the minimum useful fields for debugging 4xx/5xx failures.
- **Prewarm observability is outcome-only:** the Codex HTTP-bridge prewarm canary experiment finished, so its bucket/cohort dimensions were retired (issue #1340 phase 4). The `codex_lb_http_bridge_prewarm_total` counter is labelled by `outcome` only, request logs record `prewarm_status` / `prewarm_latency_ms` (statuses: `not_applicable`, `skipped`, `success`, `timeout`, `error` — `canary_miss` no longer occurs). The legacy `prewarm_canary_bucket` / `prewarm_eligible_reason` request-log columns stayed declared but unwritten through v1.22–v1.24; `retire-prewarm-canary-column-mappings` removed them from the ORM model and allow-listed the retained physical columns in the schema-drift gate, because a previous-release replica still maps them and renders explicit NULLs in its INSERTs while the migration Job runs ahead of the workload roll. The Alembic drop revision ships the release after (see the next-release queue in `openspec/specs/deployment-installation/context.md`).
- **Source Responses timings fall back to proxy measurement** (`measure-source-response-timings`, 2026-10-19). A valid upstream vLLM-style `metrics` pair still wins. Otherwise `SourceDispatch` measures timing itself:
  - Start: the send to the source.
  - TTFT: the first visible frame, judged by the subscription classifier and stamped at handoff to the client. HTTP stamps after ownership publication; WebSocket stamps inside the send lock.
  - End: the first relayed terminal. When no terminal was relayed, the end is `finish()` entry.

  Chat-completions and audio routes stay metrics-only. Before this change, about 14,900 source rows a week carried no timing at all.

  Consequences:
  - Non-stream and compaction rows get `latency_ms` only.
  - Source TTFT includes network time, relay queueing and ownership writes.
  - Reports medians and the Grafana TTFT panels now include source rows. Only the 24-hour breakdown separates them by upstream transport.

  Rationale, the blank-row list and a worked example are in `openspec/changes/archive/*-measure-source-response-timings/context.md`.
- **TTFT datasource selection stays in Grafana:** the Helm chart packages the
  TTFT dashboard but does not provision a PostgreSQL datasource or its
  credentials. The visible, single-select `DS_SQL` variable keeps
  installation-specific datasource UIDs out of chart values while routing all
  four SQL panels through one explicit selection.

## Operational Notes

### Native WebSocket queue pressure

Raw helper events and decoded messages share queue-byte accounting. The default helper budget is
256 MiB and each connection is capped at 128 MiB. The API-focused HA profile sets
`CODEX_LB_NATIVE_WEBSOCKET_BUFFER_MAX_BYTES=1073741824` inside each 3-GiB container. A separate
setting is needed to avoid applying that larger budget to stock 1-GiB deployments. Object sizes
and queue bookkeeping are included; active parsing/processing/native-process memory is not.

The reader and pump yield every 32 events. For example, 128 small deltas followed by completion
are delivered in order even if the consumer starts later, without blocking send acknowledgements.
An over-budget connection reports `proxy_websocket_buffer_exhausted` with failure phase
`consumer_backpressure` and bounded numeric details (`connection_queue_bytes`, `connection_limit_bytes`,
`helper_queue_bytes`, `helper_limit_bytes`, `incoming_bytes`). Accepted messages precede the terminal
failure. Raw payloads and credentials are not included in diagnostics.

This is local overload: direct and HTTP-bridge relays settle pending requests without penalizing
the selected account or replaying ambiguously accepted work. Consumption, discard, abandoned-queue
collection and shutdown release queue charges. Already-waiting receivers still receive a terminal
signal during close. Native HTTP queue limits and upstream quota/owner failures are separate work.

- Use request ids to correlate inbound proxy logs, outbound upstream traces, and client-visible failures.
- Prefer summary tracing in normal debugging sessions; enable payload tracing only when the exact normalized outbound request matters.
- For direct compact `5xx` failures, look for `proxy_compact_failure` alongside `upstream_request_complete`; together they show the compact failure phase, failure detail, exception type, retry metadata, and affinity source.
- After the Grafana sidecar imports the TTFT dashboard, select the ordinary
  PostgreSQL datasource that points to the codex-lb database from the visible
  **PostgreSQL** dropdown. A datasource registered only as a frontend runtime
  plugin is not listed by Grafana's datasource variable.
- Timeout invariant violation logs describe startup `Settings` and imported
  constant validation only. They intentionally avoid request-scoped overrides,
  runtime-derived effective timeout values, payloads, API keys, access tokens,
  raw affinity keys, account emails, and other high-cardinality identifiers.

## Abandoned shared waits (2026-10-19)

A shared future whose every waiter has already given up (routine after an SSE keepalive timeout) has its exception consumed once, so it no longer surfaces as an "exception was never retrieved" ERROR log (upstream #2427, `openspec/changes/backport-upstream-october-reliability-2`). Waiter and cancellation semantics are unchanged.

## Source failure codes (2026-10-21)

Source-routed Responses rows used to keep only codex-lb's own `model_source_response_failed`, so a relay's failure frame (for example a 169-byte `error` frame from `ch-relay`) left no trace and triage needed a packet capture. The shared Responses stream parser (`SourceStreamUsageParser`) now keeps the first valid failure code in `SourceUsageHolder.terminal_error_code`. `SourceDispatch.write_row()` stores that code in `upstream_error_code` for non-success rows. Because the code is captured in the shared parser, it covers the HTTP SSE stream, the native source WebSocket session and the WebSocket→HTTP bridge.

- Only the code (or the type, if no code is present) is kept, and only when it matches `^[a-z0-9][a-z0-9_.:-]{0,63}$`. The message is never read, because WebSocket clients must keep seeing the redacted `Model source failed the response` (see `model-source-websocket`).
- The first valid failure wins. A relay that sends `error` and then a synthesized `response.incomplete` still records the `error` code.
- Telemetry maps codes outside `_SAFE_UPSTREAM_ERROR_CODES` to `other`, so source-specific codes stay on the instance.

Example row: `status=error`, `error_code=model_source_response_failed`, `upstream_error_code=upstream_eof`, `upstream_status_code=200`.


## Bridged source stream trace (2026-10-23)

Non-success rows of WebSocket turns bridged to an HTTP/SSE source carry a payload-free `failure_detail`, for example `source_bridge events=created,in_progress,metadata handed_off=none replay=eligible`.

- `events`: up to eight event kinds from a fixed vocabulary, with consecutive repeats collapsed and `+` marking that more followed.
- `handed_off`: the furthest class handed to the client transport (`none`, `prefix` or `content`), latched at the transport-handoff point.
- `replay`: whether the attempt qualified for the single pre-content replay. A failure before the relay started reads `events=none handed_off=none replay=none`.

Each started replay logs `source_bridge_replay request_id=… replacement_request_id=… reason=…`. A replay that could not be prepared logs `source_bridge_replay_unavailable`.

Query: `select failure_detail, count(*) from request_logs where failure_detail like 'source_bridge %' group by 1`. See the change `replay-pre-content-bridged-source-failures`.
