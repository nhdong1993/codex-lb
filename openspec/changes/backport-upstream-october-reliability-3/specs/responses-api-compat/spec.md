## ADDED Requirements

### Requirement: Direct WebSocket session anchors remembered as denied are retired instead of re-injected

When a direct Responses WebSocket `response.create` carries no client `previous_response_id`, Codex session affinity is enabled, and session continuity holds a completed-response anchor (`last_completed_response_id`) that the process-local stale previous-response memory records as denied for the request's API key id, the service MUST NOT inject that anchor. Before the stored-prefix comparison it MUST retire the anchor from session continuity — clearing the completed response id, the stored input count, the stored input prefix fingerprint, and the pending tool-call metadata that exist only for that anchor — so the same id cannot be injected again once the stale memory entry expires. The service MUST log `websocket_session_anchor_retired` with `reason=stale_previous_response` for the retired anchor. The request MUST then be dispatched with the client's own untrimmed `input`, without `previous_response_id`, and its request state MUST NOT be marked as carrying a proxy-injected anchor. The stale memory MUST be consulted with the same API key id the fail-closed path used when it remembered the denial. This rule MUST NOT alter a client-supplied `previous_response_id`, and a continuity anchor that is not remembered as denied MUST keep the existing injection behavior.

#### Scenario: Full-context retry after a denied injected anchor goes upstream unanchored

- **GIVEN** a direct Responses WebSocket session whose continuity state holds `last_completed_response_id = resp_denied_anchor` with a matching stored prefix and pending tool-call metadata
- **AND** an earlier turn on that anchor failed closed with `previous_response_not_found` without a retry-safe fresh replay, so `resp_denied_anchor` is remembered as stale for the request's API key
- **WHEN** the client re-sends its full context as a `response.create` without `previous_response_id`
- **THEN** the upstream payload carries no `previous_response_id`
- **AND** the upstream `input` is the client's full untrimmed input
- **AND** the request state is not marked as carrying a proxy-injected anchor
- **AND** continuity no longer holds `resp_denied_anchor`, its stored input count, its prefix fingerprint, or its pending tool-call metadata
- **AND** the service logs `websocket_session_anchor_retired … reason=stale_previous_response`

#### Scenario: Anchor not remembered as denied is still injected

- **GIVEN** a direct Responses WebSocket session whose continuity anchor is not remembered as stale for the request's API key
- **WHEN** the client sends a follow-up whose input prefix matches the stored context
- **THEN** the service injects `previous_response_id = last_completed_response_id` and trims the stored prefix exactly as before

#### Scenario: Client-supplied anchor is never retired by this rule

- **GIVEN** a direct Responses WebSocket `response.create` that carries its own `previous_response_id`
- **WHEN** the session-anchor decision runs
- **THEN** no session anchor is injected or retired
- **AND** the client's `previous_response_id` is forwarded unchanged

### Requirement: Anonymous upstream output frames belong to the created response

When more than one request is pending on a single upstream WebSocket (an HTTP bridge session or a direct WebSocket session) and an upstream `response.*` frame other than `response.completed`, `response.failed` or `response.incomplete` arrives without a response id, the proxy MUST deliver that frame to the pending request whose response upstream has already created (its response id is known), when exactly one such request exists, regardless of whether that request is still visible or is draining after downstream cancellation. The proxy MUST NOT deliver such a frame to a sibling request that is still waiting for its own `response.created`. Anonymous `error`, `response.completed`, `response.failed` and `response.incomplete` frames and vendor telemetry frames that are not `response.*` events (for example `codex.rate_limits`) MUST keep their existing ownership rules, including targeting the request whose `response.create` is still unacknowledged. When no pending request, or more than one pending request, already has a response id, the pre-existing ownership rules apply unchanged.

When payload archiving is enabled on the direct WebSocket path, archive attribution MUST use the same anonymous output ownership rule as relay processing, including attribution to a draining created owner.

#### Scenario: Archive and relay agree on the created owner

- **GIVEN** a direct WebSocket with payload archiving enabled, request A with a known response id, and request B waiting for its own `response.created`
- **WHEN** an anonymous `response.output_text.delta` arrives
- **THEN** the frame is archived under A's archive request id, not B's
- **AND** relay processing accounts the frame to A and forwards its bytes unchanged

#### Scenario: Pipelined sibling does not receive the created response's output

- **GIVEN** an HTTP bridge session with request A whose `response.created` has arrived
- **AND** request B on the same session has sent `response.create` and is waiting for its own `response.created`
- **WHEN** upstream emits `response.output_item.added` and `response.output_text.delta` without a response id
- **THEN** both frames are delivered to request A's downstream stream
- **AND** request B's downstream stream receives nothing

#### Scenario: Draining sibling that gave up does not swallow the created response's output

- **GIVEN** request A's `response.created` has arrived on a shared bridge session
- **AND** request B on the same session is draining after its downstream closed before its own `response.created`
- **WHEN** upstream emits an anonymous output frame
- **THEN** the frame is delivered to request A

#### Scenario: Cancelled created response keeps its output away from a visible sibling

- **GIVEN** request A's `response.created` has arrived and A is draining after downstream cancellation
- **AND** request B on the same session is visible and waiting for its own `response.created`
- **WHEN** upstream emits an anonymous output frame
- **THEN** the frame is attributed to request A's drain
- **AND** request B's downstream stream receives nothing

#### Scenario: Anonymous error still targets the unacknowledged request

- **GIVEN** request A's `response.created` has arrived on a shared bridge session
- **AND** request B on the same session is waiting for its own `response.created`
- **WHEN** upstream emits an `error` frame without a response id
- **THEN** request B is failed with that error
- **AND** request A remains pending and receives nothing

#### Scenario: Anonymous completion keeps existing terminal ownership

- **GIVEN** an HTTP bridge or direct WebSocket with two visible pending requests, A with a known response id and B waiting for its own `response.created`
- **WHEN** an anonymous `response.completed` arrives
- **THEN** B is removed and finalized while A remains pending and receives no event accounting
- **AND** the HTTP bridge delivers the completion to B's queue
- **AND** direct WebSocket archive attribution uses B's archive request id and forwards the frame unchanged

#### Scenario: Leading telemetry still targets the unacknowledged request

- **GIVEN** request A's `response.created` has arrived on a shared bridge session
- **AND** request B on the same session has just sent `response.create`
- **WHEN** upstream emits a `codex.rate_limits` frame without a response id
- **THEN** the frame is attributed to request B

#### Scenario: Two visible created responses leave an anonymous frame unmatched

- **GIVEN** exactly two requests are pending on one upstream socket, both visible and both with a response id
- **WHEN** upstream emits an anonymous output frame
- **THEN** the frame matches no request and is recorded as unmatched upstream liveness, as before this change

## MODIFIED Requirements

### Requirement: Per-request detached-session retire sweep bounds its lock wait

The fail-safe sweep that reconsiders detached HTTP-bridge generations on every bridge request MUST use one five-second monotonic deadline for its aggregate detached-session lock waits. Each retirement attempt MUST receive only the remaining time. Once the deadline expires, the sweep MUST stop starting attempts and emit one warning naming the number of unattempted sessions, if any. Timed-out and unattempted sessions MUST remain tracked with their lock state untouched for later sweeps and lifecycle cleanup. Session lifecycle owners (drain, close, cooldown-suppression retirement) MUST keep waiting for the lock without a bound so retirement decisions stay authoritative. Request cancellation MUST NOT bypass the shielded finalization sweep or transfer resource cleanup ownership.

#### Scenario: Busy detached lock does not park the request path

- **GIVEN** a detached session flagged `retire_after_drain` whose `pending_lock` is held by another task for longer than the bound
- **WHEN** a request runs the fail-safe sweep
- **THEN** the sweep returns after the bound without closing the session
- **AND** if sessions remain unattempted when the deadline expires, one warning reports their count
- **AND** the timed-out session remains tracked for later sweeps and lifecycle cleanup
- **AND** the lock remains owned by its holder with no stranded waiter

#### Scenario: Free detached lock still retires

- **GIVEN** a detached session flagged `retire_after_drain` whose `pending_lock` is free and which no turn owns
- **WHEN** a request runs the fail-safe sweep
- **THEN** the session is retired exactly as before

#### Scenario: Lifecycle owners keep the unbounded wait

- **GIVEN** a drain or close path calls the retire check without a bound while another task briefly holds the lock
- **WHEN** the holder releases
- **THEN** the retire check proceeds and retires the session

#### Scenario: Several busy sessions share one deadline

- **GIVEN** three detached sessions and a five-second sweep budget
- **WHEN** the first retirement attempt consumes three seconds and the second consumes its remaining two seconds
- **THEN** no third attempt starts and aggregate lock waiting is five seconds
- **AND** the deferred sessions remain tracked and a later sweep can retire them

#### Scenario: Cancelled request finalization uses the same deadline

- **WHEN** a bridge request is cancelled while several detached sessions have busy locks
- **THEN** shielded finalization uses one aggregate lock-wait deadline before cancellation propagates
- **AND** deferred sessions retain their existing cleanup owners

