## Context

See proposal.md. The admission helper wraps one database-backed lookup, but SQLAlchemy does not wrap every error from asyncpg connection creation. Both bridge reuse branches currently reject excluded hard-key candidates before the existing goal-restart capability is consumed by guarded selection.

## Goals / Non-Goals

Goals: contain lookup failures before dispatch, preserve cancellation, and let the existing restart authorization remain the sole authority for owner replacement.

Non-goals: broaden restart classification, bypass file/conversation ownership, change account health policy or add a configuration option.

## Decisions

- Normalize exceptions at the narrow model-evidence lookup boundary. Failure to read evidence is always a local admission failure, regardless of driver exception inheritance. Cancellation remains uncaught because it is a BaseException. Enumerating only SQLAlchemy exceptions failed on a real connection-refused probe; enumerating driver subclasses would couple proxy policy to driver implementation.
- Independent review reproduced the same issue in cold account selection and direct WebSocket reuse/final admission. Share the proxy model-admission helper across selection and both transports. Direct WebSocket reuse converts the normalized error to its existing request-local rejection path; final admission already has request-local `ProxyResponseError` handling.
- Give the shared required-owner predicate the already-classified restart capability, and defer to guarded selection when it is present. Apply the same predicate in cached and in-flight reuse. The selector still verifies persisted owner status, assignment/security scope and atomic sticky ownership before abandonment.
- Extend route regressions using SQLAlchemy's async driver connection boundary with deterministic failing connectors, plus the actual sticky selector for restart tests. Include controls for healthy-but-excluded owners and restart-shaped requests with dependencies.
- Consume agreeing Free observations only after metadata sync succeeds. A failed generation/token-guarded write retains evidence for the remaining bounded attempt; credential replacement and paid samples keep their existing evidence-reset behavior. Generation-fenced clearing after persistence cannot discard a replacement generation's evidence.
- Iteration 2 extends request-local error handling to the real initial WebSocket selector and initially fenced ordinary evidence clearing with the observed refresh-token ciphertext. Clear takes the account-row lock before evaluating the credential/generation conditions, preserving replacement-before-child lock ordering on PostgreSQL. A rotation may defer cleanup; it cannot discard another credential's observations.

## Risks / Trade-offs

- A lookup programming failure also becomes a retryable admission failure → log its exception type and keep the boundary limited to evidence lookup; never convert send errors here.
- Restart capability accidentally weakens hard ownership → test active owners, file/previous-response dependencies, canonical replacement and in-flight creation.
- Large dirty workspace obscures review scope → direct the independent reviewer to the plan-verification/bridge changes and preserve unrelated work.

## Final-review correction: replacement generation

The third and final independent review reproduced two routine-rotation races: exact-token fencing retained Free evidence contradicted by a paid sample, and suppressed first-Free enqueue after successful rotation. Token ciphertext cannot identify credential replacement. A persisted integer `Account.credential_generation`, initialized to zero, now advances only at the existing transactional import/reauth replacement boundary. Rotation leaves it unchanged. Evidence fingerprinting, clear and priority enqueue/current checks use that generation; existing guarded metadata writes still protect exact-token snapshots and retain evidence if they lose a rotation race. This also fences replacement with identical token values.

The additive migration follows the priority-check revision, backfills historical accounts with zero and leaves token/plan/status values untouched. New replicas require the migration first. An old application version does not advance the new generation on replacement, so generation-based fencing cannot promise replacement isolation during mixed-version execution of replacement operations. No production rollout is part of this task. The final fixes are verified by targeted SQLite/PostgreSQL tests and local checks; the skill's three-review limit precludes a fourth independent review.
