## Context

OAuth token persistence and auth.json import each construct an account before calling the shared identity-aware repository. New accounts currently inherit the database's disabled warm-up default. Existing-account replacements copy credential fields while retaining operator preferences.

## Goals / Non-Goals

**Goals:** Automatically enroll newly created accounts through both authentication entry points and preserve existing warm-up choices.

**Non-Goals:** Change global defaults, trigger a probe during login, change quota thresholds or scheduling, or backfill existing accounts.

## Decisions

- Explicitly initialize `limit_warmup_enabled=True` in both account-creation services. This makes the authentication policy clear without changing defaults for unrelated database inserts or requiring a migration.
- Reuse the repository's credential-only replacement behavior. Do not assign the flag after an upsert, since the returned account may already exist with an explicit opt-out.
- Keep global warm-up disabled by default. An enrolled account receives traffic only when the operator enables the global switch and the normal scheduler eligibility checks pass.

## Risks / Trade-offs

- An account imported as a genuinely separate slot is new and becomes enrolled even if a sibling slot opted out. Tests distinguish new slots from credential replacements.
- During a rolling deployment, accounts added through an old replica retain the old default until that replica is replaced. The behavior applies to auth handled by the updated application.
- Warm-up consumes a small amount of quota. Operators retain both the global switch and the per-account opt-out.
