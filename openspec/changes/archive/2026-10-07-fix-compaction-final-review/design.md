## Context

The compact collector receives complete SSE events and already keeps validated
scalar usage from earlier events. The terminal `response.completed` event can
also carry usage at the event root, while the response object may omit or set
usage to null. Request policy can materialize a provider-facing reasoning
alias on either Responses request model before source dispatch.

## Decisions

1. Inspect terminal usage sources separately from the earlier observed usage.
   A non-null terminal usage payload must pass the existing strict typed usage
   schema and reject negative input/output/total/detail counters. Invalid usage
   leaves the collected usage absent without entering the earlier-counter
   fallback, so limited-key finalization returns `usage_unavailable`. A valid
   terminal payload keeps precedence. Null or absent terminal usage may use
   observed counters as before. Ordinary source Responses parsing is unchanged.
2. Add the provider-reasoning materialization marker to compact requests, set
   it for either request model when policy fills the effort, and copy it during
   compact-to-Responses conversion. Existing source payload shaping then
   removes only proxy-added reasoning effort when policy does not require the
   alias; client-supplied reasoning remains intact.
3. Keep the existing ownership, settlement, cleanup and subscription routing
   paths unchanged. Regression tests exercise the public HTTP routes rather
   than only helpers.

## Risks / Trade-offs

Invalid terminal usage is deliberately fail-closed even when an earlier event
was valid, avoiding a silent accounting substitution. Provider aliases remain
present when an API-key policy requires canonical reasoning, so policy-owned
behavior is unchanged.
