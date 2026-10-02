## Context

See proposal.md for the three reproduced failures. Priority checks already have a generation fence and bounded attempts. Both transports already own unsent cleanup and strict continuity checks; the fix should use those paths.

## Goals / Non-Goals

Close the demonstrated ordering gaps without adding schema, configuration, or a second source of plan evidence. Preserve replacement fencing, global health neutrality, strict ownership and accepted sibling lifetime. Authentication policy and UI rendering are unchanged.

## Decisions

- A first Free sample from a separate refresh advances the existing check generation even when the old check is still running. A priority worker already owns its retry and does not enqueue its own first Free observation, so it does not invalidate itself. Preserve request time and attempt count; use the existing delayed follow-up. A new persisted dirty flag would duplicate this fence and require a migration.
- Move the final model lookup before the existing synchronous reconnect latch check. Reuse the unsent handoff and lease release path instead of treating a known closed socket as an uncertain send failure.
- Check shared model evidence during bridge reuse and before submit. Keep account-global availability separate because exclusion applies to one model. Reuse existing retirement and selection for movable turns; strict owners fail closed. Late rejection uses proven pre-dispatch cleanup, preserving sibling turns.

## Risks / Trade-offs

- Additional bridge evidence reads add latency; read the bounded cached-session snapshot before acquiring the registry lock, then recheck the candidate at submission.
- New await points can change socket lifetime; tests coordinate reader close and admission waits and assert ownership/settlement, not only successful responses.
- The two-minute window and three-attempt cap remain binding. Exhausted verification falls back to ordinary fleet refresh.

## Example

A check processes Plus, then a fleet refresh records Free before the check finishes. The new generation remains pending after the old completion and the next Free sample confirms the downgrade. For bridge routing, a peer rejecting A/model M stops a cached A bridge from sending another M frame; a conversation pinned to A fails without moving to B.
