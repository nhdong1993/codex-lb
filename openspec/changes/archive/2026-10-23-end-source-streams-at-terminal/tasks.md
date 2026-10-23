## 1. Specification

- [x] 1.1 Write the proposal, context and `model-source-routing` delta. Run `openspec validate end-source-streams-at-terminal --strict`.

## 2. Tests (red first)

- [x] 2.1 Route (`/v1/responses`, limited key): for a source that keeps its body open after `response.completed` or `response.failed`, assert that the stream ends, the source is closed, the row and reservation are correct, and no admission remains in flight. This timed out before the fix.

## 3. Backend

- [x] 3.1 `_source_stream_body` stops after the chunk that completes the terminal.

## 4. Verify and ship

- [x] 4.1 Run the targeted suites serially, plus ruff and ty.
- [x] 4.2 Run `/review-impl`, sync the delta into `openspec/specs/model-source-routing/` (spec and context), and run `openspec validate --specs`.
- [x] 4.3 Deploy. Confirm that HTTP `model_source_idle_timeout` rows and gateway requests of 290 s or more disappear for completed streams.
  - Deployed 70ba7e7c2 at 2026-10-24 00:00 HCM.
  - The deployed `stream_responses` was driven against live ch-relay. The body ended at 3.85 s, together with `response.completed`; before the fix it was still open at 420 s.
  - No HTTP-route traffic had reached the source yet.
- [x] 4.4 Archive after the operator accepts the result. Accepted 2026-10-24 HCM.
