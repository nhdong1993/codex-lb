## Diagnostic evidence — 2026-10-01 UTC

- Full function-call history completed with the exact diagnostic result through the remote endpoint, CLIProxyAPI and the codex-lb public response route before the configuration repair. Ordinary text and one successful call are therefore insufficient health checks.
- The same full history generated on credential slot 1 was accepted on slots 1, 3 and 5. Slot 4 instead returned `response.completed`, `input_tokens=0`, and text saying it could not perform a function call. Response ID: `resp_0bddeefc71eac9a6016abe311e3c5c87d09584fff38f5381cb`. This establishes a failed synthetic continuation, not general permission to migrate account-owned state.
- A separate slot 4 own-history test ended after `response.function_call_arguments.delta`, without a terminal event. Both results support temporary quarantine even though its earlier plain-text probe succeeded.
- HTTP requests with only a prior response ID and a tool result failed at the remote endpoint with `No tool call found`. Full history succeeded. The deployed CLIProxyAPI binary correctly reconstructed WebSocket history against a controlled local upstream; a separate fixed-credential remote test also retained the tool result.
- The six 409s at 09:46–09:47 could not be conclusively attributed to this client/model. A recorded client response at 09:47 had zero input tokens, matching the shape of the synthetic failure but not proving identical account selection.

## Applied configuration

At 10:11:47 UTC, used the authenticated management configuration endpoint to set `routing.session-affinity: true` and Code Hole credential slot 4 `weight: 0`. The loaded normalized configuration differed only in those two settings. Upstream WebSockets remained disabled on all five credentials. The codex-lb source remained HTTP only.

Private backup: `/home/dong01/cpa-manager-runtime/backups/linxaq-session-repair-20261001T101147Z/config.yaml` (mode 0600, parent 0700). Redacted outcome report: `/home/dong01/cpa-manager-runtime/linxaq-session-repair-20261001.json` (mode 0600). No credentials or request transcripts are included in this change.

The live CLIProxyAPI log confirmed reload followed by a session-affinity cache miss and then a hit on the same credential for the first validation pair. All three HA backends and CLIProxyAPI retained their previous start times and healthy status.

## Verification

- Function-result round trips through CLIProxyAPI and the public codex-lb route completed and returned `FUNCTION_RESULT_VERIFIED`. One assistant added explanatory text, failing the initial whole-string assertion but retaining the exact result marker and 665 input tokens.
- The first namespace/custom probe was malformed (missing namespace description); its 400 was a test-input error. After correcting it, a subsequent round trip encountered upstream Cloudflare HTML 502s across three eligible credentials. This is a remaining upstream availability limitation, not a successful verification.
- A new valid custom-tool round trip then completed through the public codex-lb route and returned `CUSTOM_RESULT_VERIFIED` with 643 input tokens. Final response ID: `resp_07cab77a0754b2dc016abe32b743e887d0a7576a67ae54899f`.
- The final binding pair selected slot 1 twice (miss then hit). The persisted slot 4 weight remained zero. Zero input usage on a tool-call turn also occurred in a successful exchange, so zero usage alone is not a failure detector.
- `openspec validate stabilize-cliproxy-source-continuation --strict` passed. `openspec validate --specs --strict` passed all 67 capabilities. No application code changed; application rebuild and unit-test repetition were unnecessary.

Completeness: all four tasks verified. Correctness: the two intended loaded settings, functional results and process health were checked. Coherence: existing controls were used; no ownership bypass, token replacement, source migration or HA restart occurred. This verifies the scoped runtime repair, not a permanent cure for remote tunnel failures or all historical 409s.
