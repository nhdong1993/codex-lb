## Context

See proposal.md. Shared downgrade observations already enforce two Free samples; the fleet scheduler selects one account at a time. Subscription snapshots are daily. Existing OAuth refresh claims and status compare-and-set distinguish transient failures from revoked credentials.

## Goals / Non-Goals

Accelerate suspicious account checks independently of fleet size, expose pending verification, and avoid repeated routing to a rejected account/model pair. Do not reduce confirmation thresholds, rotate credentials because a plan changed, change pinned ownership, or redesign the fleet scheduler. Production deployment and account reauthentication are separate operator actions.

## Decisions

- Add one ephemeral `account_plan_checks` row per account. It binds to the existing stable identity fingerprint, retains request/attempt times, a three-attempt budget, completion state, and the most recently rejected model. A two-minute request cooldown coalesces repeat errors; entries expire and are cleaned by the scheduler. Credential replacement and account deletion remove them.
- A lifespan-owned scheduler checks every five seconds under the existing leader lease, claims at most three rows atomically, and uses one independently owned session per worker. Claims reserve a bounded execution window; stale completions cannot overwrite replacement requests. First Free observations request verification after 15 seconds; model rejection requests it immediately. Failed/unconfirmed attempts retry after 15 seconds within the budget. No background task survives scheduler shutdown.
- Reuse the usage updater with forced freshness and all existing workspace/credential checks. Refresh subscription with its existing 30-second manual throttle before usage confirmation; failures in one check do not prevent the other. Keep successful old metadata on upstream failure. A confirmed plan change invalidates routing selection caches.
- Extract the rejected model from the already recognized entitlement message. Enqueue through existing request-owned cleanup tasks and filter that account/model pair for two minutes through shared database evidence, without rewriting global account health. Preserve owner resolution and existing strict-pin failure behavior.
- Add an optional account summary `planCheckPending` flag, derived from matching uncompleted bounded work. While true the shared subscription component suppresses the old countdown and displays verification text. Free/unknown plans suppress countdowns defensively. Delayed manual subscription responses cannot overwrite the current pending flag.

## Risks / Trade-offs

- Slow upstream or a large simultaneous batch can exceed the 30–60 second target; attempt bounds, leases and three workers prevent unbounded pressure.
- Model rejection alone does not prove Free; only usage evidence changes the plan, and an active paid response completes verification without reauthentication.
- Refresh-token revocation is upstream state; this change cannot restore revoked credentials. Existing login/import clears old evidence.
- Temporary model exclusion retains only the latest rejected model per account, bounding storage; it never excludes unrelated models or claims account-wide failure.

## Migration Plan

Add a table after the current single head, with a cascading account foreign key and a due-work index. Historical account rows and credential bytes remain unchanged. Verify upgrade/downgrade/upgrade and schema drift against isolated databases; no production migration is performed during implementation.
