# Native model-source WebSocket planning context

## Purpose and proposed scope

The requested plan covers `client → WebSocket → codex-lb → WebSocket → source`. It assumes a provider implementing the Responses WebSocket protocol on the source's existing Responses endpoint. The alternative `client → WebSocket → codex-lb → HTTP/SSE → source` is a separate feature and is not necessary for this first native transport.

The normative behavior is in [model-source-websocket](specs/model-source-websocket/spec.md) and the [Responses compatibility delta](specs/responses-api-compat/spec.md). [design.md](design.md) records implementation choices; [tasks.md](tasks.md) is the execution checklist. The runtime, management capability, catalog, installer and local acceptance tests are implemented. See [verification.md](verification.md) for evidence and remaining provider/client staging checks.

## Why the scope is bounded

Removing the existing rejection guard would send source models through subscription credentials. Reusing the account session wholesale would also apply account health, OAuth refresh and subscription-only payload transformations. A dedicated source session can instead reuse the mature source ownership and settlement rules.

Sequential turns cover the basic prompt/tool-result loop. Multiplexing, steering, portable live-socket migration and automatic fallback after uncertain dispatch multiply the ownership and billing states; they need separate acceptance contracts.

## Example

An operator configures source A with base URL `https://provider.example/v1`, Responses support, WebSocket support and streaming model alias `team/model=upstream-model`.

1. The client connects to codex-lb's `/v1/responses` and sends `response.create` for `team/model`.
2. The proxy authorizes the public alias, admits the turn and connects to `wss://provider.example/v1/responses` with A's credential. It sends `upstream-model` upstream.
3. Response identifiers are bound durably to the caller/public alias/source revision before delivery. Client-visible model fields remain `team/model`.
4. The client submits tool results with `previous_response_id` over the same socket. The proxy rechecks permission and uses the existing connection.
5. If the connection is lost, a reconnect still targets A. If A cannot recover that response state, the client receives a continuity error and can explicitly restart with full context. Source B never receives A's opaque continuation.

HTTP-only sources retain their HTTP/SSE route. Enabling this flag does not translate a Chat Completions server into a Responses WebSocket server.

## Protocol evidence and verification limits

The [official Responses WebSocket guide](https://developers.openai.com/api/docs/guides/websocket-mode), consulted on 2026-09-29, describes `response.create`, optional `generate:false`, connection-local continuation state, and newer multiplexed lanes. These establish a reference protocol; they do not prove any configured third-party source supports it. The proposed first version intentionally supports a smaller sequential subset, with unsupported extensions rejected explicitly.

No real provider credentials or external inference were used. The provider conformance check and actual-client fallback check remain tasks. Local fixtures verify the native protocol and accounting paths but do not certify a provider or a particular client release.

## Dependencies and operations

Coordinate installer activation with `disable-install-websockets-only-for-source-assignments`; otherwise a correctly implemented source route can remain unreachable from generated source-only client config. Preserve the HTTP-only fallback option for mixed-capability pools. Refresh client catalogs/config after enablement; use normal request logs to verify the actual transport and source.

Stable context is now in `openspec/specs/model-source-websocket/context.md`, with linked user documentation at `docs/model-source-websocket.md`. Keep this change active until the remaining provider/client and release verification is complete.

## Implementation and review slices

The installer policy already present in the working tree was preserved for mixed, account-only and unassigned keys. The source-only decision now additionally uses the complete authorized Responses pool. No overflow setting or subscription health behavior was added. Runtime budgets reuse existing settings; the source flag is the only new capability.

Prepare focused review slices in dependency order when publishing: (1) additive migration and management/UI capability, default off; (2) shared candidate resolution, event observation and dispatch metadata with HTTP regressions; (3) native adapter/session and route integration, splitting adapter tests and public lifecycle acceptance into focused commits as needed; (4) catalog/installer activation and documentation. Do not advertise transport support from an intermediate build lacking the runtime. No PR, commit, push or deployment was requested or performed here.

The tested local upstream is a deterministic aiohttp WebSocket fixture. It covers two turns on one connection, tool results, warmup, missing usage, failures, ownership publication, aliases, queueing, cancellation, drain and handshake retry boundaries. A real external provider was not selected, and no existing production source was enabled.
