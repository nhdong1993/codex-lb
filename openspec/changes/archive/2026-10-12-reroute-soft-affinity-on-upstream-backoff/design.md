## Context

Production telemetry from 2026-10-12 01:35–02:35 UTC contains 241 upstream overload/processing errors across 13 accounts. Qualified failures already feed a three-rejection/120-second replica-local window, but soft owners only move after three such trips. Upstream generation latency itself cannot be repaired by the proxy.

## Goals / Non-Goals

Move later, independently submitted soft-affinity requests off sustained failures as soon as existing evidence establishes backoff. Do not replay an accepted request, move opaque account-owned state, alter upstream timeouts or persist account health globally.

## Decisions

- Use the existing overload deadline, not the combined burst/overload predicate: one code-less 429 must not move a warm owner.
- Reuse the existing isolated-owner selection and provisional sticky mutation flow, including cap-aware replacement selection, secondary-budget filtering, probe ownership and fallback to the original owner when no sibling is selectable.
- Keep the isolation duration setting responsible only for escalation duration; zero still leaves ordinary sustained-overload backoff effective.
- Rename the internal helper/diagnostic to describe backoff rather than isolation. No public error taxonomy changes.

## Risks / Trade-offs

Earlier movement can lose prompt-cache locality. Require the existing three qualified failures and an eligible sibling, preserving lone-pool operation. Hard continuity and ambiguous ownership must retain their current checks. Tests cover cap-exempt owners, capped alternatives, expiry, burst-only cooldown and the public request path.

## Migration Plan

No migration. Local advisory state remains per replica. A separately authorized HA rollout is needed for runtime behavior; code changes alone do not repair production upstream latency.
