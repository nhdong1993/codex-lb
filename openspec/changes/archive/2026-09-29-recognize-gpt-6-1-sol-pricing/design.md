## Context

Native prices in `app/core/usage/pricing.py` feed request-log persistence, dashboard cost breakdowns, aggregate estimates, API-key reservations, and settlement. No current entry or alias recognizes GPT-6.1 Sol. Its official model page establishes distinct cached-input pricing.

## Goals / Non-Goals

**Goals:** Recognize GPT-6.1 Sol consistently across existing consumers, retaining independent model identity and published tier/context rates.

**Non-Goals:** New configuration, new billing dimensions, historical data rewrites, routing/model-discovery changes, and production deployment.

## Decisions

- Add a dedicated `ModelPrice` and family-specific suffixed alias, following existing GPT-6 patterns. Mapping to GPT-6 Sol would overcharge cached input and merge aggregate model identities.
- Use the existing priority multiplier and Flex/long-context fields. The existing calculator already applies the correct threshold and tier multipliers, so no new calculation branch is needed.
- Extend existing parametrized unit and route integration tests for exact names, aliases, cache deductions, tier/context boundaries, reservation admission, and completed settlement.
- Preserve historical persisted costs and quota counters. Request-detail fallback for null costs remains available through the shared pricing path; aggregate backfill is outside this change.

## Risks / Trade-offs

- Cached-input differences can be hidden by uncached-only tests → verify explicit cached-cost breakdowns and keep old Sol expectations.
- Missing a pricing consumer could leave cost-based quotas ineffective → test request-log API output and quota admission/settlement through real HTTP routes with stubbed upstream responses.
- Static prices can age → document the official source and verification date in context.
