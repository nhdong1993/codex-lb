# Context: route source-only models off a subscription owner pin

## Purpose and scope

On the direct Responses WebSocket, recorded subscription-account continuity must not send a turn to a subscription account when that account cannot serve the model. The rule applies only to *source-only* models: a model that an enabled or disabled Responses-capable model source claims, where none of its candidates (the raw client model, or the API key's enforced model when one is set, and the normalized model) is in the subscription model registry. Such a turn is refused with the existing service-level `model_source_requires_http_transport` (503), so Codex retries it over HTTP. The refused turn does not reach a ChatGPT account, which would answer with a terminal 400.

The normative text is in the [responses-api-compat delta](specs/responses-api-compat/spec.md) ("Previous-response source routing follows proven ownership", plus the aligned sentence in "A disabled model source refuses its models instead of falling through") and the [model-source-websocket delta](specs/model-source-websocket/spec.md). This document does not restate them.

Out of scope: HTTP Responses routing, handshake-time transport policy, and in-proxy WebSocket-to-HTTP translation.

## Incident example (2026-10-15, production)

Request `ws_363b6f50d7ac42bf86601e1d777739d4` came from Codex Desktop 0.162.0-alpha on `/v1/responses` over WebSocket, with an API key without source assignment scoping. `http/gpt-6-astra` exists only on the OpenAI-compatible source `ch-relay`. That source is HTTP-only (`supports_responses_websocket=false`), and the slug is not in the subscription model registry.

| Time (UTC) | Frame on the same socket | What the proxy did |
| --- | --- | --- |
| 04:00:19 | `response.create` `{"model":"gpt-6.1-sol","generate":false,...}` (warmup) | Subscription model. Routed to ChatGPT account A. Request logs record A as owner of the warmup response `resp_W`. |
| ~04:00:21 | `response.create` `{"model":"http/gpt-6-astra","previous_response_id":"resp_W",...}` | The source preflight found A recorded as the owner of `resp_W` and returned to subscription routing. The connect and reuse source guards were both skipped because an owner was recorded. The turn was sent to account A. |
| ~04:00:21 | upstream `error` 400 `invalid_request_error` "The 'http/gpt-6-astra' model is not supported when using Codex with a ChatGPT account." | Terminal. The `account_model_unsupported` replay cannot move a `previous_response_id`-anchored turn, every ChatGPT account rejects the slug, and Codex treats 4xx as terminal. |

The same API key had 5 such failures between 03:51 and 04:00Z. HTTP requests for the same model in the same Codex session went through `ch-relay` and succeeded.

After this change, the second frame is answered in-band with the service-level `model_source_requires_http_transport` (503), and no upstream frame is sent. Codex falls back to HTTP and resends full context without `previous_response_id`, and the HTTP route forwards that request to `ch-relay`.

## Root cause

The 2026-09-09 change `preserve-previous-response-source-ownership` replaced response-ID syntax inference with recorded ownership. It made a recorded subscription owner a veto over source routing on HTTP and WebSocket alike. Its WebSocket scenario assumed "a source is also configured for the requested model", meaning the subscription account could also serve the model.

For an unscoped API key, `responses_source_model_candidates` drops every candidate that is in the subscription model registry. So a model that is source-routed under such a key is never a registry model, and no subscription account can serve it. For these models the owner veto does not preserve working continuity. It guarantees a terminal 400.

A Codex warmup makes this easy to trigger. The warmup binds the socket and records an owner for a subscription model, and the next turn switches to a source model with that warmup as its anchor.

## Decisions

- **Gate on "no registry candidate", not just "source-owned".** If any candidate is a registry slug, a subscription account can serve the model. A source-scoped key can route a registry slug to an assigned source, and then the recorded anchor is real, so keeping the owner wins. Candidates are the ones source selection already uses: the raw client model, or the API key's enforced model when one is set (`effective_model_for_api_key`), and the normalized model. For example, an alias whose normalized form is a registry slug stays on the old precedence.
- **Count disabled sources as claiming the model.** This matches `responses_model_is_source_owned`. A disabled source's model can't be served by a subscription account either. After the HTTP fallback, Codex resends without the anchor and gets `model_source_disabled` there, which names the actual condition.
- **Apply the same check to the turn-state owner branch.** The preflight returns to subscription routing when a client-supplied `x-codex-turn-state` resolves to a subscription account under the same key, just as it does for a recorded `previous_response_id` owner. A turn-state-only anchor did not cause the incident's 400. Without a `previous_response_id`, no previous-response owner is recorded, so the mixin source guards already refused the turn. Checking both branches gives the preflight one owner rule, and it moves the refusal ahead of admission and request-log preparation. The observable differences are listed under "Behavior changes beyond the incident path".
- **Return a 503 service-level failure, not a terminal 4xx.** Codex falls back to the HTTP transport only on a service-level WebSocket failure. A 4xx is shown to the user and the turn is lost. This is the same reason the existing connect guard and the disabled-source WebSocket scenario use 503.
- **Don't forward to the source over WebSocket, even if the source supports native WebSocket.** The anchor (`resp_W`) lives on the subscription account. The source cannot resolve it and would fail the turn as an unknown previous response, or worse, if the identifier happened to collide. Dropping the anchor inside the proxy would silently discard client context. Codex's HTTP fallback resends full context, which is the safe recovery.
- **Leave structural exclusions and required-capability routing first.** Terminal `compaction_trigger` and `input_file` references are account-bound by construction. Security routing must not degrade along an undocumented path.
- **Leave HTTP out of scope.** The incident was WebSocket-only. Codex's HTTP transport resends full context, so in practice it does not carry a subscription anchor on a source-model request.

## Behavior changes beyond the incident path

The refusal is raised in the WebSocket source preflight (`_prepare_source_websocket_turn` in `app/modules/proxy/api.py`), in both owner branches. Besides the incident shape (a recorded `previous_response_id` owner on a first turn or on a subscription-bound socket, which used to get the subscription 400), these cases change for a source-only model:

| Socket state and anchor | Before | After |
| --- | --- | --- |
| First turn, turn-state owner only | 503 `model_source_requires_http_transport` from the mixin connect guard, with a request-log row | Same 503 from the preflight, with no request-log row |
| Reused subscription-bound socket, turn-state owner only | Terminal `response.failed` from the mixin reuse guard | In-band service-level 503 `model_source_requires_http_transport` |
| Socket bound to a native source session, previous-response or turn-state subscription owner | 409 `websocket_reconnect_required`, because returning to subscription routing counted as a backend change | 503 `model_source_requires_http_transport`, because the turn now goes to neither backend |

The mixin connect and reuse guards in `app/modules/proxy/_service/websocket/mixin.py` are unchanged. For a source-only model they are now reachable only through the precedence this change deliberately keeps: required-capability routing (`requires_subscription`) or a structural subscription exclusion.

## Constraints

- The refusal is raised before source admission, usage reservation and request-log preparation, so it holds nothing that needs releasing and writes no request-log row.
- No new setting, schema or error code. `model_source_requires_http_transport` and its 503 status already exist.
- A socket that a subscription warmup bound earlier is not reconnected or rebound. Only the offending turn is refused.

## Failure modes and edge cases

- **Client does not fall back on an in-band 503.** The turn still fails, but with an explicit, actionable code instead of the opaque 400. Operator remedies are listed below.
- **Lookup failure.** The preflight keeps its fail-closed `model_source_lookup_failed` (502), and that includes the source-only check on its owner branches, which runs before any reservation. The unchanged mixin guards keep their fail-open `responses_model_is_source_owned` lookup, which only matters on their remaining capability-routing and structural-exclusion paths.
- **Registry shadowing.** A source that lists a registry slug does not trigger the refusal for an unscoped key. The slug stays on subscription routing, which is unchanged.
- **Compaction trigger with a source-only model and a recorded owner.** This still goes to the subscription owner because of the structural-exclusion precedence, and the upstream may reject it. That behavior is accepted and unchanged by this change.
- **Known remaining gap (HTTP).** A non-Codex HTTP client that sends `previous_response_id` pointing at a subscription-owned response, together with a source-only model, still gets the subscription 400 under the HTTP owner veto. Fixing that would need its own change with an HTTP-specific outcome, for example a 409 ownership error or dropping the anchor.

## Operator notes

- **Symptom before the fix:** request logs for a source model show `transport=websocket`, `account_id` set, `model_source_id` empty, and `error_code=invalid_request_error` with "The '<model>' model is not supported when using Codex with a ChatGPT account". Those turns usually follow a `generate:false` warmup on the same socket within seconds.
- **After the fix:** the refusal writes no request-log row. Its only trace is the application log line `Websocket model source requires http transport model=... raw_model=... stage=subscription_anchor anchor=previous_response|turn_state`. Successful HTTP requests for the model, with `model_source_id` set, should follow it.
- **Interim mitigation without deploying:** use a provider profile with `supports_websockets=false` for source models, such as the host-local `codex-lb-custom` profile, or a source-only API key. The handshake then returns HTTP 426 under "Source-only handshakes honor effective HTTP-only capability" in `model-source-websocket`.

## Related specs and changes

- `openspec/specs/responses-api-compat/spec.md`: "Previous-response source routing follows proven ownership" and "A disabled model source refuses its models instead of falling through".
- `openspec/specs/model-source-websocket/spec.md`: "Source WebSocket routes retain source authorization and payload semantics" and "Source-only handshakes honor effective HTTP-only capability".
- `openspec/changes/archive/2026-09-09-preserve-previous-response-source-ownership/`: introduced the owner veto.
- `openspec/changes/archive/2026-10-12-deny-http-only-source-websocket-upgrades/`: made `ch-relay` HTTP-only and added the source-only handshake 426.
- `openspec/changes/add-model-source-websocket/` (active): it still carries deltas for all three requirements this change modifies: "Previous-response source routing follows proven ownership" and "A disabled model source refuses its models instead of falling through" (`responses-api-compat`), and "Source WebSocket routes retain source authorization and payload semantics" (`model-source-websocket`). Coordinate archive order so that its spec sync does not revert this change.
