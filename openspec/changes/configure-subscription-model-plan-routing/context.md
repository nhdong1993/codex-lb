# Subscription model Plan routing context

## Purpose and decisions

The requested targets are native subscription models, not OpenAI-compatible
model sources. An operator restriction therefore belongs in dashboard settings,
independently of upstream `available_in_plans` capability metadata. The default
is `{}`: installation and migration do not seed any model-specific restrictions.
Removing an entry restores that model's existing selection behavior.

The restriction is an intersection, not a preference: exhausted, unavailable,
out-of-scope, or unentitled Free accounts produce the existing routing error
instead of spending paid capacity. Upstream entitlement, health, quota, key
scope, single-account selection, and ranking still apply. Ownership is resolved
before routing eligibility; filtering cannot invent a unique conversation owner
or move file-/conversation-bound work to another account.

## Identity and representation

Keys match exact effective native model IDs after existing alias/API-key handling.
They are case-sensitive and cannot contain whitespace. API configuration does
not require current catalog membership. The UI selects native non-image entries
and retains saved absent IDs for editing/removal; it does not offer source-only
or image-only entries as native choices. A source resolved by existing dispatch
is unaffected even when its slug collides with a configured native slug.

Recognized operator plans are `free`, `plus`, `pro`, `prolite`, `team`, `business`,
`enterprise`, and `edu`. Case and surrounding whitespace are normalized and
lists are deduplicated. Equality is strict: `prolite` does not satisfy `pro`.
Catalog plan labels can be broader than this operator-setting vocabulary;
adding a catalog entitlement does not automatically add a configurable plan.

## Constraints and failure modes

- Omitted or null `modelPlanRoutingPolicies` preserves the mapping; only `{}`
  clears it. Invalid updates fail atomically. Existing authorization, audit,
  version conflicts, and settings propagation apply.
- One non-null JSON-text settings column avoids a second policy source of truth.
  Historical rows receive `{}`. Upgrade is idempotent; downgrade discards this
  mapping, so re-upgrade starts empty while unrelated settings are preserved.
- Policy cache fingerprints distinguish selection pools. Propagation uses the
  existing five-second settings cache and cross-replica invalidation, not
  instantaneous cluster-wide linearizability.
- Warm bridge/WebSocket admission reads current persisted account plans in an
  owned database session outside the bridge registry lock. It rechecks after
  admission waits. Policy rejection is local unsent work: accepted siblings,
  task ownership, reservation settlement, and strict owners remain protected.
- Malformed stored JSON or unavailable policy evidence fails closed with a
  sanitized local admission error, not an upstream health penalty. Restriction
  changes do not terminate already accepted work.
- An invalid stored mapping (manual SQL edit, or a saved plan that is no
  longer recognized) keeps native routing failing closed, but settings stay
  readable: `GET /api/settings` shows only the still-valid entries and logs a
  warning. Every settings save writes the mapping it carries, and an omitted
  field carries that displayed mapping, so a PUT of `{}` or a corrected mapping
  repairs the stored value. For example, stored
  `{"gpt-6-luna": ["free"], "retired-model": ["retired-plan"]}` reads as
  `{"gpt-6-luna": ["free"]}` while native requests return 503 until a save.
- The final direct-send recheck applies only to configured models and reads
  only the persisted account plan. Unconfigured models dispatch as before;
  plan-check rejections recorded by concurrent requests stay selection-time
  evidence that fails over normally.
- Same-account retries after an upstream 5xx or 401 pass the final recheck
  before resending. A confirmed pre-dispatch connect failure instead moves a
  movable stream through fresh selection, which admits only the currently
  effective pool; if that pool is empty, the existing exhausted-retry error
  surfaces. An upstream 401 on an allowed first send keeps its existing health
  penalty; only the admission denial itself is health-neutral.
- Mutation and refetch keep UI controls busy. A conflict refreshes mapping and
  version and resets stale drafts; an ordinary failure leaves a retryable draft.

## Example and post-deployment operational note — not applied

After a **separately authorized deployment**, an operator may use
`PUT /api/settings` with the following payload and `expectedVersion` from a fresh
`GET /api/settings` when applying optimistically:

```json
{
  "modelPlanRoutingPolicies": {
    "gpt-5.6-terra": ["free"],
    "gpt-5.6-luna": ["free"],
    "gpt-6-luna": ["free"]
  }
}
```

This payload is an example operational action, not a seeded default or an
unchecked feature gate. **It has not been applied.** No deployment, live settings
change, production database operation, restart, commit, or push is authorized
by this work. For example, if only paid accounts are usable after this mapping
becomes effective, a request for `gpt-6-luna` fails rather than falling back to
paid; an unconfigured native model or a source-dispatched model is unchanged.

## Author integration status

Author evidence and exact commands are in [verification.md](verification.md).
Normative requirements and stable context are synced to `account-routing`
after author checks, **before independent review**, so the reviewer sees the
combined diff. This is not review approval. Independent review and archive
remain unchecked; no change is archived. Global nonstrict validation is the
mandated repository check. Existing global strict long-requirement warnings
are baseline limitations, not a reason to rewrite unrelated requirements;
new requirements must introduce no strict diagnostics. The reproduced baseline
architecture and API-key cache failures are recorded separately; this author
neither fixes them nor grants gate exceptions. The independent reviewer decides
which gates apply. The direct HTTP final-dispatch/same-account retry
correction was integrated and verified on 2026-10-13; see verification.md for
the commands, results and the remaining unrelated baseline failures.
