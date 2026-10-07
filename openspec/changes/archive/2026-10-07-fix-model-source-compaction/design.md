## Context

The diagnosis and synthetic production evidence are in [context.md](context.md).
Source HTTP Responses already implements source assignment, public aliases,
credential revision ownership, quota and deterministic cleanup. Compact bypassed
that dispatcher and selected subscription accounts.

## Decisions

- Use HTTP Responses with a terminal trigger for all source compact operations.
  No provider names, automatic `/compact` probing, schema or configuration are
  introduced. Providers that do not support the trigger return their normal
  error; they do not silently retry through subscription credentials.
- HTTP Codex trigger requests use the existing source SSE path. Standalone
  compact requests reuse the same source dispatch with a bounded stream
  collector and return only a real encrypted compaction item. Keep WebSocket's
  existing structural compaction behavior outside this HTTP correction.
- Build the source request from retained input before subscription-only compact
  trimming. Normalize standalone v1 triggers to one terminal trigger, preserving
  the existing compatibility contract; native malformed triggers remain 400.
- Resolve source ownership using the exact effective body, then use the existing
  non-stream finalizer to publish the compact response/item/encrypted ownership
  before returning JSON. Bound collection by the compact and source timeout,
  close on the first terminal, and never retry a consumed stream. Compact history
  and its terminal trigger are protected from input-replacing source overrides;
  other effective reference overrides retain the existing ownership checks.
- Record compaction explicitly on source dispatches and retain cached/reasoning
  token observations when supplied. A new replica resolves returned state from
  the shared ownership database, independent of local source rotation state.

## Validation

Use a real local HTTP provider fixture at the public API paths, including slash
variants, alias/auth wire assertions, source pool continuation, disabled and
changed owners, unknown/conflicting state, subscription/file precedence,
upstream errors, truncated streams, cancellation, timeout and settlement failure.
No production deployment or credential change is part of this implementation.
