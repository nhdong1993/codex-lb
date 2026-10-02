# Native Responses WebSocket for model sources

The contract is [spec.md](spec.md). This capability forwards native JSON WebSocket traffic from a Responses client through codex-lb to an explicitly opted-in OpenAI-compatible source. Existing sources default to HTTP/SSE until enabled. SSE streaming alone does not imply native WebSocket compatibility.

## Configuration and example

In **Settings → Advanced settings → Model sources**, enable **Responses WebSocket** together with **Responses** and model **Streaming**. The management API field is `supportsResponsesWebsocket`; omission on PATCH preserves the value. Setting it true while Responses is false is rejected. Selecting WebSocket in the dashboard also enables the dependencies; disabling either dependency clears the checkbox.

A source with base URL `https://provider.example/custom/v1` and public alias `team/model` pointing to `provider-model` connects to `wss://provider.example/custom/v1/responses`. Only that source's API key is sent upstream. Both `/v1/responses` and `/backend-api/codex/responses` support explicit trailing slashes.

```json
{"type":"response.create","model":"team/model","input":"Hello"}
```

A follow-up includes its `previous_response_id` and tool output or new input. The proxy keeps one upstream connection, one active turn and at most one waiting turn. The waiting turn has no quota reservation and spends its request budget while queued.

## Supported profile and failures

The supported subset is sequential `response.create`, JSON response events and `generate:false` warmup. Named `stream_id`, steering, application `response.cancel`, binary messages and background responses are rejected. Closing the downstream connection cancels the active session. Payload size, upstream buffering, idle time, sends and per-turn lifetime are bounded using existing proxy settings and the source timeout. Socket count uses the existing proxy WebSocket bulkhead.

The source capability defaults false. Opt in only after testing the provider's actual WebSocket endpoint, warmup and tool continuation. A provider that accepts HTTP Responses but has no native WebSocket endpoint stays HTTP-only. The local test fixture does not certify a third-party provider or a particular Codex release.

A reconnect preserves source ownership, not the contents of the former upstream connection. Provider-local response state may be unavailable on the new connection. The proxy returns a failure without removing the anchor or replaying the request against another source. The client can explicitly start over with full context. Switching public model, source, upstream alias or credentials requires reconnect.

A recognized missing previous response keeps the existing recovery classifier: `previous_response_not_found` on the Codex-native route and `stream_incomplete` on the public route. The message is sanitized; provider details and the missing ID are withheld. Ordinary initial payload validation errors keep the socket available for a corrected create, including errors found only after handing input to subscription validation. The backend binds after preparation succeeds. For example, an unsupported subscription image file reference can be corrected by sending a valid source create on the same socket.

Shared preparation uses the established WebSocket domain-error formatter. A revoked key retains `authentication_error`, model/reasoning policy rejection retains `permission_error`, and exhausted source quota retains `rate_limit_error`. Supplied parameters survive; for example, a forbidden effort still identifies `reasoning.effort`. This applies before backend selection, including subscription-only requests, and after source socket reuse. Upstream provider failures continue through their separate redaction path.

Security requirements inherited through parent tasks, session IDs, turn state or previous responses are resolved before selecting a source, including references introduced by source overrides. Lookup failure stops routing. During a subscription transport outage, the source handshake exemption checks effective model policy; an unrelated source cannot exempt a key forced to a subscription model.

An explicit turn-state header with a subscription owner under the same API key keeps that ownership, even without `previous_response_id`. Conflicting or unavailable owner lookup stops dispatch. A synthesized turn-state placeholder returned by an earlier source connection can reconnect when it has no subscription owner. Source overrides that introduce a subscription-owned previous response also require a reconnect instead of crossing backends.

HTTP and WebSocket share source revision hashes and the ownership store. Output references are published before events reach the client. Failover is limited to a portable initial request with a proved pre-send connection/handshake failure, up to five sources. A send failure is never replayed automatically.

Selection may lose an admission slot while effective policy is being read. A portable initial request then tries another eligible source, with at most five candidates and no extension of the original deadline. The replacement's capability, controls and ownership are checked before quota acquisition. A bound socket or owned continuation does not move sources after losing admission.

## Accounting and operations

Each generation owns admission and quota settlement independently of the reusable socket. Success uses provider usage; a limited key with missing usage uses the existing estimate. Warmup uses input accounting with zero estimated output. Failure and truncated responses release their reservation. A disconnect after content uses the existing cancellation estimate. Estimated values are not presented as observed usage in logs.

If disconnect or a send timeout races a terminal event, an observed failure still releases quota and a successful terminal handed to the transport keeps successful settlement. The session closes without sending a contradictory second error. A terminal waiting for ownership publication or the downstream write lock has not been delivered. For example, a successful `generate:false` warmup without usage still settles estimated input when the client closes during the terminal send.

Reported usage in a withheld terminal does not turn pre-content cancellation into delivery. If the client disconnects before any content has been handed to its transport, native settlement releases the reservation even when that terminal carried usage. Previously delivered content retains the existing cancellation accounting policy.

Responses turns use `http_responses_stream_request_budget_seconds` through the same budget helper as subscription WebSockets. The selected source's own timeout can shorten that deadline. The generic proxy request budget, including dashboard overrides, is the fallback only when the stream-specific setting is absent. Connect and downstream idle timeouts retain dashboard overrides. For example, with a generic budget of 60 seconds, stream budget of 7200 seconds and source timeout of 3600 seconds, an active turn is not cut off at 60 seconds. A shorter stream budget still expires the turn.

Retry preparation spends the original request budget and keeps the earliest source timeout already applied to the generation, including when a replacement source allows more time. A timeout closes the source connection before returning its inference slot. Session lifecycle ownership starts before initial policy and source lookup. A separate observer handles disconnect, expired drain and active deadlines even when acquisition, ownership publication or settlement defers cancellation. Session teardown closes both transports before waiting for persistence, waits at most the existing cleanup budget or remaining drain deadline, and leaves unfinished work in the service's tracked cleanup set. Database recovery can therefore complete the original settlement without keeping the socket or ASGI scope alive. For example, if quota acquisition commits after timeout, tracked cleanup releases that reservation once without contacting the provider.

While initial lookup runs, one reader preserves raw input and receipt times in a buffer bounded to 16 frames and 16 MiB. A subscription handoff receives those frames in order without source normalization; excess read-ahead closes the socket with a best-effort queue error. After selecting a source, only one waiting create is admitted behind the active turn. Receipt time, including time spent in preparation, counts against each waiting request's budget.

The first source create and reused source messages share a 16-MiB limit on the original UTF-8 JSON text. Whitespace and JSON escapes count toward the limit; reserializing the parsed object would lose that information. A rejected first create holds no admission or quota and leaves the socket available for corrected input. Subscription-bound messages retain their existing larger ingress allowance. For example, adding whitespace past 16 MiB to a source create produces `invalid_request_error` even when its parsed body is small.

An active reservation heartbeat retries after a transient database error. This matters for explicitly configured long generations: a single failed touch must not let the stale-reservation reaper reclaim a live reservation. Each touch uses its own background session; cancellation still stops and awaits the heartbeat.

Request logs identify `transport=websocket`, `upstream_transport=openai_compatible_websocket`, public model and source identity; no subscription account or OAuth state is created. A failed source handshake does not update the subscription WebSocket failure marker. Global HTTP transport still rejects ordinary handshakes with 426. Drain rejects new turns and closes idle/expired sessions while finalizing admitted work.

Upgrade all replicas and apply the additive migration before enabling the flag. Keep it false during a mixed-version rollout. Existing connections cannot migrate between HA replicas. Test the intended provider and client in staging, then enable the source and regenerate the client installer. To stop new source WS turns, disable the flag; previously admitted work completes cleanup. Production deployment is separate from this change.

Discovery is conservative: all enabled, permitted Responses candidates for a public model must stream and support native WS before `prefer_websockets` becomes true. For source-only keys, installer WS support additionally requires a nonempty entirely capable model set and global policy permitting it. Other key classes retain their installer policy. The installer flag is frozen when exported; rerunning an old script refreshes the catalog only. HTTP-only source errors after upgrade preserve `model_source_requires_http_transport`; actual client fallback behavior must be checked with the intended client release.

Catalog and installer capability follow effective model routing, including key enforcement, exact source aliases, canonical fallback and fast-mode prohibition. They evaluate the whole permitted pool for the model that will actually receive the request. For example, an enforced `gpt-5.4-high` alias can use a capable canonical `gpt-5.4` source when no exact source alias exists. With fast mode prohibited, an enforced `gpt-5.4-fast` instead uses `gpt-5.4`; a capable fast-alias source cannot enable WebSocket when the canonical source is HTTP-only. An explicitly configured non-prohibited alias keeps its own source precedence.

Allowlisted names without an eligible Responses source do not enter the installer's aggregate capability decision. For example, a capable Responses model and a Chat-only model can share an allowlist without disabling WebSocket for the Responses model. Disabled, unassigned and unknown models behave the same way. An eligible Responses source that lacks streaming or native WebSocket support still disables the aggregate, and an empty eligible set or an enforced model without an eligible source keeps WebSocket disabled.

The ownership helper is shared by HTTP and WebSocket, so it creates the existing
HTTP error envelope before transport adaptation. For example, after an HTTP
response publishes `resp_A`, disabling its source makes a continuation return
409 `previous_response_owner_unavailable` with `type=server_error`, even when
that source never enabled WebSocket. An output-item reference uses
`model_source_owner_unavailable` with the same type. Neither denial starts a
provider attempt or reserves quota. This preserves the classification of
unavailable upstream state rather than treating it as malformed client input.
