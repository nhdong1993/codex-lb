## Context

See proposal.md for the reproduced failures. Priority evidence and enqueue already share an account-row lock on PostgreSQL and a SQLite writer section. Bridge lookup distinguishes cache affinity from a required file/conversation account, and submit already has request-local cleanup for `ProxyResponseError`.

## Goals / Non-Goals

Goals: preserve confirming work under delayed enqueue, resolve the actual required account, and keep local SQL failures on pre-dispatch cleanup.

Non-goals: schema changes, new retry budgets, changed account health policies, or changes to accepted request ownership.

## Decisions

1. Guard both first-Free INSERT and reopen UPDATE with shared evidence matching the account fingerprint, Free plan, and count one. Evaluate after the existing account lock. This uses durable evidence and prevents a delayed enqueue from fencing a worker that already consumed confirmation; adding timestamps or generations to observations is unnecessary. Model-rejection enqueue keeps its existing behavior.
2. Reuse the preferred-account matching rule when deciding whether an excluded session is a required owner. Put the combined predicate in the existing reuse helper to keep cached and in-flight checks identical without growing the bounded bridge mixin. Before detaching an excluded cached or in-flight generation, mark it for retirement after drain: visible requests and reserved handoffs retain their existing lifecycle owner until settlement; an idle generation still closes immediately.
3. Wrap bridge model-evidence reads in a small admission helper that catches SQLAlchemy database errors and raises a sanitized `ProxyResponseError(503)`. Apply it to cache, in-flight, fallback and final-submit checks. Cancellation remains uncaught. Existing request-local cleanup then releases resources without treating the failure as an upstream send error.

## Risks / Trade-offs

- Evidence changes during SQL lock waits → test a real PostgreSQL transaction overlap as well as the externally visible account-summary race on SQLite.
- Required-owner mismatch could weaken continuity → retain same-owner fail-closed tests and cover a different file owner on both routes and after in-flight creation.
- Failure cleanup can affect accepted siblings → hold a real accepted bridge response open, inject database and pool failures, assert reservation/admission release and sibling completion.

## Migration Plan

No schema or configuration migration. Validate focused integration suites on SQLite and PostgreSQL, run repository checks, synchronize the specifications, and archive after verification. Deployment is a separate operator action.
