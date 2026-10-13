## Context

One shared CLIProxyAPI instance serves three codex-lb HA backends. Its five Code Hole credentials use weighted round robin without session affinity. Upstream WebSocket transport is already disabled because the remote endpoint rejects it. The codex-lb source currently advertises HTTP only.

## Goals / Non-Goals

**Goals:** remove the reproduced failing credential from selection and stabilize healthy multi-turn requests using existing controls.

**Non-Goals:** infer that all historic 409s or blank app turns have the same cause, discard encrypted history, replace source credentials, add automatic retries after tool output, or change HA runtime state.

## Decisions

- Set credential slot 4 weight to zero; preserve the token and model aliases. An own-history retry also truncated, so keeping it in the pool is not justified by its successful single-message probe.
- Enable session affinity with the existing default one-hour TTL and subagent behavior, preserving weighted selection for new sessions. This is a global CLIProxyAPI control; the shared instance applies bindings before reaching upstream regardless of the codex-lb replica.
- Save a private configuration backup and use the authenticated management endpoint for a validated live reload. Compare normalized configuration before/after, allowing only the intended routing and credential-weight changes.
- Validate exact tool-result markers, explicit terminal events and nonzero input usage. HTTP 200 alone is insufficient. Do not label every text-free completion an error: tool calls and prewarm are valid.

## Risks / Trade-offs

- Session affinity can move a session when its credential becomes unavailable; it is not an ownership guarantee or an encrypted-history migration mechanism.
- The remote endpoint can still have tunnel or account failures. Quarantine reduces capacity by one credential and requires a later operator retest before re-enabling it.
- The six observed 409s lacked enough attribution to establish the affected user/model. The existing fail-closed ownership contract remains authoritative.

## Migration Plan

Back up the runtime YAML with mode 0600, update the two existing controls through management, verify the loaded config and container uptime, then run functional probes. Record evidence in change notes and stable operating guidance in model-source-routing context. No database migration or application rollout is needed.
