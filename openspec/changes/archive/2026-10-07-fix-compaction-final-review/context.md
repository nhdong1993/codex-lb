# Final compaction review corrections

The fresh review reproduced invalid terminal-root usage returning HTTP 200
with stale 21/8 counters after a terminal reported negative or incomplete
counters. It also reproduced strict providers rejecting compact requests with
`thinking: "minimal"` because conversion added `reasoning.effort`, while the
equivalent terminal-trigger route preserved the original alias and succeeded.

The collector must distinguish absent usage from present invalid usage. For
example, earlier 21/8 counters followed by terminal-root input -1 must return
`usage_unavailable` for a limited key, release quota and withhold encrypted
output. Null terminal usage can still use the earlier 21/8 counters.

Reasoning provenance is private request metadata; copying it through conversion
lets the existing source shaping logic preserve provider aliases without
changing client-supplied effort or API-key enforcement. These fixes add no
settings and leave ownership, replay and subscription contracts intact.

The first re-review confirmed reasoning provenance and found that the general
usage parser clamps negative detail counters and ignores total tokens. Terminal
compact validation now checks strict field types and nonnegative input, output,
total, cached and reasoning values before exposing the usage object. Twelve
HTTP cases reproduced negative total/detail acceptance before this correction.
The existing limited-key finalizer rejects absent collected usage; no fallback
is attempted after a non-null invalid terminal payload.
