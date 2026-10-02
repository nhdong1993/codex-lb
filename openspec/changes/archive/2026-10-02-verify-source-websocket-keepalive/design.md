## Context

The production fix sets `ping_timeout=None` on the source transport. A mocked factory assertion does not show that the route finishes when the upstream accepts pings without sending pongs, or that application deadlines still release reservations.

## Goals / Non-Goals

Bound keepalive resources and test successful and unsuccessful public-route lifecycles using local upstream servers. Production probes, deployment, new timeout settings and unrelated pending changes are outside this review.

## Decisions

Use a source-specific `ClientConnection` through the supported `create_connection` factory hook. Its library-owned keepalive task sends protocol Ping frames through the existing send context, without allocating acknowledgment futures or enforcing a pong deadline. The source does not consume latency measurements. This avoids dependency-version-specific pending-ping dictionaries and retains transport flow control and cancellation on connection loss. Ordinary explicit `ping()` calls retain the library's behavior.

Keeping the library keepalive unchanged would retain one future per unanswered ping across arbitrarily many successful turns. Disabling all pings would break the keepalive contract. The source-specific loop changes only these fire-and-forget keepalive probes, with connection lifecycle ownership retained by the library.

Use an aiohttp WebSocket with automatic pong handling disabled. Accelerate the transport's ping interval and its fallback timeout only inside the test factory; retain every explicit production connection option. Observe a real ping before proceeding, and withhold its pong while continuing response events. The regression must fail if the production `ping_timeout=None` option is removed.

Test both canonical route families and trailing-slash forms for success, and both families for first-frame timeout, stream-idle timeout and actual upstream close. Check one provider dispatch, exactly-once request logging, finalized/released reservations and zero source admission after teardown. Continue using existing total-turn deadline tests.

Record review results and baseline type-check failures separately from scoped checks. Correct the earlier proposal's unimplemented diagnostic promise and synchronize operating context without claiming the production cause was measured conclusively.

## Risks / Trade-offs

- Short wall-clock heartbeat intervals could race slow CI. Synchronize on observed pings, use generous receive bounds and enforce the regression by mutation rather than by exact elapsed-time assertions.
- A synthetic provider cannot prove every production disconnect has the same cause. Document the evidence and the remaining uncertainty.
- The custom keepalive uses the library's send context and protocol sender. Verify against the locked dependency and keep connection closure/late-pong regression coverage when upgrading it.
