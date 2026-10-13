## Scope and rationale

Five selected upstream fixes improve security and failure handling without the schema removals in the full release. Sources: #2453/#2454 (`986a9bf1`, `74dddf21`), #2496 (`f8ffbac2`), #2119 (`da70ac5d`), #2255 (`3b75bb2d`), and #2449 (`143e07d0`).

## Constraints and preservation

Keep source WebSocket ownership, API-key usage groups, UTC+7 reset logic, byte budgets, new-account warmup, and pending OpenAI-message isolation. Credit balance here means spendable credit, not reset-credit coupons. Do not import migrations or the already-equivalent Content-Type fix.

## Failure examples

A probe with `max_output_tokens=16` can get HTTP 400 despite valid credentials. A weekly-exhausted account with `credits_has=true` and a missing balance is not evidence of spendable credit. During drain, a new WebSocket should receive HTTP 503 with Retry-After instead of an apparent authorization failure. A terminal without a code containing "The usage limit has been reached" needs the same health treatment as coded exhaustion, but an invalid_request_error quoting that sentence must not bench the account.

## Operations

All validation uses synthetic data. No production requests that consume quota are used. Commit, push, and deployment require separate authorization. The unrelated workspace is not part of this change.
