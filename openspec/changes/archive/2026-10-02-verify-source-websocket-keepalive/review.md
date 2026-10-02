# Review evidence

Scope: the uncommitted source WebSocket pong-timeout patch and its tests/specification. Other pending work in the shared checkout is excluded. No branch, commit, push or deployment is part of this review.

## Confirmed findings

| ID | Severity | Category | Location | Finding | Resolution |
| --- | --- | --- | --- | --- | --- |
| R1 (Codex P2) | Medium | testing | `tests/unit/test_model_source_websocket_transport.py:43` | Mocked connection options did not establish response and accounting behavior when a provider withholds pongs. | Added sixteen route regressions covering both route families, trailing slashes, two-turn continuity, deadline failures, real peer closure, late pongs and client cancellation. |
| R2 | Medium | convention | `openspec/changes/archive/2026-10-02-fix-source-websocket-pong-timeout/proposal.md` | The archived proposal promised new close diagnostics and route coverage that were absent; causal wording exceeded the production evidence. | Removed the unimplemented diagnostic promise, added route coverage and operating context, and qualified production attribution. |
| R3 (Codex P2) | Medium | performance | `app/modules/model_sources/websocket.py:73` (original patch) | Unanswered ping futures accumulate across successful turns on a reused socket; per-turn deadlines do not bound connection lifetime. | A source connection subclass emits periodic protocol pings without acknowledgment futures, using connection-owned task cleanup and flow-controlled sends. |

## Validation

- All sixteen new route regressions passed, including bounded ping bookkeeping, late pongs and client cancellation.
- Mutation: a test-only plugin restored a finite 75-ms pong deadline while the ping interval was 25 ms. The canonical public-route success test failed after receiving an error during the stream, demonstrating that it detects the original mechanism. The plugin lives outside the repository and the production code was not mutated.
- Final focused mapped suite: 36 passed, 89 deselected. Includes transport unit tests, all new route cases, total-turn stream-budget checks, first-frame rearming and no retry after send.
- Minimum dependency compatibility: the 16 new route tests plus 12 transport unit tests passed with `websockets==16.0` in an isolated `uv run --with` environment (28 passed). The lockfile/environment remain on 17.1.
- `uvx ruff check .`: passed.
- `uvx ruff format --check .`: passed, 1202 files.
- Scoped `uv run ty check`: passed for the source transport, its unit tests and the new integration tests.
- Full `uv run ty check`: two baseline diagnostics outside scope: `tests/integration/test_proxy_chat_completions.py:109` (`ProxyResponseError` envelope type) and `tests/unit/test_key_dashboard_install.py:204` (JSON container variance).
- `openspec validate --specs --strict`: 67 passed, zero failed.
- New change strict validation: passed. Review then expanded the change with a bounded-keepalive resource requirement after reproducing R3.
- R3 reproduced before its fix: one successful accelerated turn retained 11 pending ping futures. The final tests assert bounded state after each reused turn and empty state after closure.

## Codex CLI review

The first launch could not execute read-only shell commands because its inherited sandbox failed while creating loopback networking. It produced no verified verdict. The review was relaunched using the workspace's unrestricted execution policy, with explicit read-only instructions and a narrow file scope.

Round one returned two P2 findings: unbounded ping bookkeeping (R3) and missing route-level regression coverage (R1). Both were accepted under the user's explicit review-and-fix request and addressed. Round two found no actionable new or unresolved defects in scope and independently confirmed the 36-test suite on 17.1 and the 28-test suite on 16.0. The loop ended clean after two completed reviews; the initial sandbox-blocked launch was not a review verdict.

## Verification assessment

All five tasks are complete. The bounded-keepalive requirement's three scenarios map to the new delayed-pong/reuse tests, late-pong parametrization and closure/cancellation assertions. Source deadlines and settlement retain their existing implementation and mapped regression coverage. Main specification and operating context are synchronized. No scoped correctness or coherence issue remains. Full-repository type-check remains blocked only by the two recorded baseline diagnostics; no full pytest suite or production validation is claimed.

Fixes remain in the working tree with no commits, consistent with the repository's explicit-commit rule. No production deployment was requested or performed.
