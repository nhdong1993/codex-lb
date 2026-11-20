# Context: exempt reserved accounts from the subscription model Plan restriction

## Purpose

`modelPlanRoutingPolicies` is an operator routing preference ("this model goes to these Plans"). A reservation is an operator decision that an account belongs to one key. The owning key should therefore be able to use its own accounts for a restricted model; everyone else keeps the restriction.

## Decisions

- **Baseline for everyone else.** The selection-input cache is shared across keys, so the owning key gets a second load with `plan_exempt_api_key_id`. `_load_selection_inputs` drops that argument when the model is not in the snapshot it filters with, so unmapped models reuse the baseline cache key and a mapping removed between the two loads cannot hide the reserved account.
- **Admission reads the row.** `_plan_policy_rejected_ids` reads `reserved_api_key_id` with `plan_type`: an account passes when its plan is allowed or it is reserved by the request's key. Foreign or keyless requests get the same answer as before.
- **Unknown owners stay conservative.** When a `previous_response_id` owner lookup missed, the exemption could send the continuation to the reserved account although the response may live elsewhere, so that request uses the restricted pool for selection, replay and dispatch.
- **Bridge resends recheck.** Prewarm and replay sends happen after waits; on a session with an API key they recheck the restriction for the frame's model and stop if the consumer detached or the deadline passed (prewarm uses the parent request's deadline), releasing only resources the request still owns. The gate is the session's key, not the account snapshot: a token refresh during reconnect can copy a released reservation into the snapshot, so only the admission read decides. The security-work replay checks last, after its durable writes and right before send; a refusal or a cancellation there marks the re-fenced operation failed, removes the request, and returns its replacement lease; that settlement runs as one owned task a caller cancellation cannot cut short, while retirement stays in the reader task. The policy read is the last await before each send decision: resends check consumer and deadline synchronously after it, and prewarm reads it under the pending lock right before enqueue, so a reservation release or Plan change that lands during a lock wait is still seen. When cancelled, the reader still retires a drained replacement before the cancellation propagates. Keyless sessions keep their existing path.

## Limits

- The service-tier fallback for Plan-restricted models still uses the configured Plans only.
- A reused socket whose account was moved to another key's reservation keeps the existing (pre-change) exclusivity behaviour.
- For keys owning a reserved account and unmapped models the second load is normally a cache hit; an expired or changed cache key costs one more accounts read.
- Each owning key adds one selection-cache entry per mapped model, holding its own copy of the fleet snapshot until the next settings or account invalidation clears the cache. With a few reserving keys this is small; with many reserving keys on a large fleet, share the immutable fleet rows per cache generation or bound the per-key entries.

## Example

`gpt-6-luna` is restricted to `["free"]`. Key K reserves Plus `acc-r`; shared Free `acc-s` and Plus `acc-p` exist.

- K requests `gpt-6-luna` → `acc-r`.
- `acc-r` cools down → `acc-s`; `acc-p` is never selected.
- Key J → `acc-s`.
- K continues a conversation whose owner is unknown → `acc-s`.
