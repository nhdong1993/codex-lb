# Context: continue Codex sessions after a source is reconfigured

## Incident (2026-10-18)

Codex Desktop 0.163 reported, for model `ch/gpt-6-astra` on source `CLIProxyAPI`:

```
unexpected status 409 Conflict: The request's upstream state has no unambiguous available
source. Use its original source or resend portable full context without upstream-owned state.,
url: https://agent-shop.clawd.io.vn/backend-api/codex/responses, request id: b98ced8a-...
```

Evidence from production:

- The 409 came from `_resolve_source_response_candidates` (the message ending in
  "without upstream-owned state" exists only there), code `model_source_owner_unavailable`, HTTP
  `POST /backend-api/codex/responses`. Pre-dispatch refusals are not written to `request_logs`.
- `PATCH /api/model-sources/src_21c2…` (CLIProxyAPI) at 13:11:21 UTC. The first 409 followed at
  13:11:30. Bursts at 13:11–13:13, 13:20–13:21 and 13:36 match Codex's 5 retries per turn. The same
  pattern happened in the morning: 409s at 03:40–03:42, with PATCHes at 03:44–03:45.
- `request_logs.model_source_revision` for key `d2c1…` on `ch/gpt-6-astra` changed from
  `cd5573…` to `03fcd9…` at 13:11:35. Recomputing `source_revision()` against the stored rows
  shows `cd5573…` means upstream id `ch/gpt-6-astra` (no mapping) and `03fcd9…` means
  `upstream_model: "gpt-6-luna"`. The operator changed the model's upstream mapping.
- Session `…aba582` (1,495 turns over two days) stopped working on `ch/gpt-6-astra`. The user then
  switched the same session to subscription `gpt-6.1-sol`, which worked.

## Root cause

`source_revision(source, model)` fingerprints `base_url`, the resolved upstream model id and the
encrypted credential. Every reference the source produced (response id, output item ids, encrypted
reasoning, call ids) is recorded in `model_source_ownership` and in the permanent
`model_source_ownership_history` under that fingerprint. Changing the credential, endpoint or
`upstream_model` changes the fingerprint.

The candidate filter rejects a source when any owner of a request reference has a different
`(source_id, revision)`. Codex sends the whole transcript on HTTP turns (`store: false`, no
`previous_response_id`): earlier reasoning items with `encrypted_content`, and assistant
message, function-call and web-search items with their upstream `id`. So after any mapping
change, every later turn of every existing conversation on that model fails with 409. Codex cannot
resend the transcript without that state, so the user must abandon the session or switch to a
different model. History rows never expire, so the session stays broken until the transcript itself
changes (for example, after a compaction on another model).

The guard is intentional (`model-source-routing` context: "Changing a recorded owner's credential,
endpoint or upstream-model mapping invalidates its transport fingerprint"). Forwarding the opaque
state is wrong: the new transport cannot decrypt it, and with another credential it would be
cross-credential replay. Refusing the whole conversation is also more than the guard needs. The
messages, tool calls and tool results are plain content that the same operator-configured source
may receive. Only the opaque state was invalidated.

## Decision

When the only conflict for a candidate is **its own earlier revision**, project the stale prefix
of the input to a portable form and send it to that same source. Keep every other refusal.

Algorithm, per candidate `X` with current revision `r`, used only after the existing check rejects
`X`:

1. Classify the candidate's references (today's union: original-request keys | shaped effective
   keys) using the owners already loaded:
   - *foreign*: some owner has `source_id != X.id`, so do not project (no switch, no drop);
   - *stale*: every owner is `X.id`, and at least one has `revision != r`.
   Without stale keys, or with any foreign key, the existing rejection stands.
2. The client `input` must be a list. Ownership keys deliberately skip complete call/result
   pairs, including their returned bookkeeping ids (`fc_…`), so they cannot locate every stale
   item. On this path only, load owners (active and history, one extra read) for the **raw**
   `OwnershipScope.item_keys(item)` of every input item. `boundary` is the last index whose raw
   keys have an owner `(X.id, revision != r)`. If no input item carries stale state (the stale
   key is an anchor or comes from an override), the rejection stands. A lookup failure keeps
   the existing 502 `model_source_lookup_failed`.
3. If the prefix `input[:boundary+1]` contains an `item_reference`, the rejection stands, because
   stripping its id leaves nothing meaningful.
4. Project the prefix with the existing account-neutral projection
   (`project_responses_input_for_account_neutral_fresh_replay`). It drops `reasoning` items and
   completed `web_search_call` / `tool_search_*` items, and strips `id` from every other item.
   `call_id`s are kept, so call/result pairs stay self-contained. The suffix after `boundary`
   (items produced by the current revision) is forwarded unchanged. If the projected input is
   empty (for example, a request made only of old reasoning), the rejection stands.
5. Re-check with the same union rule as today, on projected views:
   - *projected original view*: the client payload with the projected input, and with replayed
     tool-call namespaces stripped (`strip_replayed_tool_call_namespaces_from_payload`, the same
     normalization shaping applies to the forwarded body), so complete namespaced pairs are
     classified the way they are forwarded. It keeps the client's `previous_response_id`,
     `conversation`, `prompt` and tools. A stale anchor therefore stays authoritative even when
     an override clears it in the effective body.
   - *projected effective view*: normal shaping of the projected request for `X` (overrides,
     tool filtering). Override evidence stays per candidate.
   The union of both key sets must be a subset of the keys whose owners were loaded in steps 1
   and 2; anything else rejects. `X` is eligible only when:
   - every remaining owner is `(X.id, r)`;
   - no unknown key was introduced only by the effective view;
   - in a pool, no unknown key at all. This replaces the pool "portable transcript" requirement,
     because the request is pinned to `X`.
   Stale anchors (`previous_response_id`, `conversation`, `prompt`, containers, vector stores),
   stale compaction `encrypted_content` and unresolved stale `call_id`s survive projection, so
   they still fail with the existing 409.
6. If eligible, store for `X` the projected effective body, its **exact** keys
   (`scope.request_keys(projected effective body)`, the existing `effective_keys_by_source`
   contract) and the projected input. The step-5 union is used for validation only and is not
   handed downstream. HTTP's dispatch guard still requires the forwarded body's keys to equal
   `resolved.request_keys[X]`. Both recorders (HTTP from the forwarded body, WebSocket from
   `resolved.request_keys`) keep recording exactly the forwarded body's keys. Step 5 proved every
   owner of those keys is `(X.id, r)` or unknown, so stale references are never recorded under
   `r`. A current-revision reference that an override removes from the effective body (for
   example, a `prompt`) is validated but neither forwarded nor recorded, the same as today. Mark
   `X` non-portable, so a failed attempt never fails over to another source. Log
   `source_stale_state_projected` with counts only.

HTTP dispatch re-shapes from the request, so it must receive the projected `input`. It then
produces the same body as step 5's effective view, which satisfies the exact-key guard. WebSocket
dispatch already forwards `resolved.payloads[source.id]` and records `resolved.request_keys`.

WebSocket scope: recovery happens on a fresh or reconnected source session. An already-bound
socket whose recorded source revision changed keeps the existing `websocket_reconnect_required`
turn error (model-source-websocket "Reused connections preserve source identity"). Codex then
reconnects, and its first create on the new connection carries full input without
`previous_response_id`. That create is projected like an HTTP turn. No automatic reconnection or
connection-identity change is added.

## Why the prefix only

Items after the boundary were produced by the current revision. Keeping their reasoning and ids
preserves reasoning continuity for turns made after the change, and keeps `fc_` ids next to
their own reasoning items. Because the boundary uses raw item keys, it covers old function-call
items whose ids are skipped by ownership enforcement. Projecting the prefix therefore removes old
ids together with the reasoning items they were linked to. That avoids "function_call provided
without its required reasoning item" upstream errors. The projection is deterministic, so the
projected prefix is byte-stable across turns and upstream prompt caching keeps working.

## Alternatives considered

- **Drop the upstream model id from the fingerprint.** Rejected. A different upstream model
  behind the same endpoint can be a different backend or account. In this incident,
  `ch/gpt-6-astra` and `gpt-6-luna` on CLIProxyAPI are different backends. The upstream would
  then fail on undecryptable state instead of codex-lb refusing it.
- **Project the whole input.** Simpler: no raw-key lookup or boundary. But every later turn of
  that conversation then loses the reasoning produced after the change, including tool-loop
  reasoning. The prefix rule costs one extra read, only on this path.
- **Strip compaction items too.** Rejected. A compaction item is the conversation's memory.
  Dropping it silently would make the model continue without the earlier context. Compacted
  sessions keep the existing 409.
- **Let other pool members take the projected transcript.** Rejected. Known ownership must not
  cause a switch.
- **A setting to enable it.** Rejected. This restores availability without loosening the
  credential fence, so it works without configuration.

## Failure modes

- Projection hides a stale anchor: impossible by construction. Only input items are projected,
  and the projected original view still carries the client's anchors.
- An override clears a stale anchor: the projected original view still holds it, so 409.
- An override reintroduces stale state: the projected effective view covers the shaped body's
  ownership keys. A post-shaping check also rejects any forwarded input item whose `id` or
  `encrypted_content` an earlier revision recorded, because complete pairs carry no ownership
  keys. Owners of override-added items are loaded with the client input.
- A stale function call outside ownership keys (complete pair): the raw-key boundary covers it.
- A retryable upstream error after projection: no failover, because the candidate is
  non-portable. The client sees the source error.
- Concurrency: resolution is read-only. Recording keeps the existing durable-before-delivery
  path.

## Example

Turn N (revision `cd5573`) produced `rs_1` (encrypted), `fc_1`/`call_1` and `msg_1`. The operator
sets `upstream_model: gpt-6-luna` (revision `03fcd9`). Turn N+1 sends:

```
[user u0, reasoning rs_1{enc}, function_call fc_1/call_1, function_call_output call_1,
 message msg_1 (assistant), user u1]
```

The boundary is index 4 (`msg_1`). The source receives:

```
[user u0, function_call call_1 (no id), function_call_output call_1, message (assistant, no id), user u1]
```

Turn N+2 resends that plus turn N+1's `rs_2`/`msg_2` (revision `03fcd9`). The boundary is still
index 4. `rs_2` and `msg_2` are forwarded unchanged.

Tool-only continuation: `[user u0, reasoning rs_1{enc}, function_call fc_1/call_1,
function_call_output call_1]`. `fc_1` and `call_1` were recorded as output-item keys under
`cd5573`. The raw item keys of the call and of its output find that owner, so the boundary is
index 3, not index 1 as ownership keys alone would give. The source receives
`[user u0, function_call call_1 (no id), function_call_output call_1]`.

## Out of scope / follow-ups

- Pre-dispatch source refusals are missing from `request_logs` (an observability gap seen
  during this investigation).
- A dashboard hint that changing a model's upstream mapping, endpoint or token resets opaque
  continuity.
