## Context

The previous rebind decides whether to generate its SQL CASE from an earlier ORM snapshot. Its validity check can therefore miss a first or repaired subscription snapshot saved before the token UPDATE. Frontend manual success merges only by account ID after cancelling list reads, even when a completed newer read changed the source.

## Goals / Non-Goals

Close the two reproduced interleavings while preserving daily cadence, strict credential ownership and unrelated account state. No schema or response changes and no new cache of subscription data.

## Decisions

- Generate the rebind for unchanged identity/plan regardless of whether the earlier ORM read had a matching subscription. In the SQL CASE require a non-null check time and fingerprint equal to the computed old credential fingerprint, plus unchanged credential and identity columns. This keeps token CAS atomic and permits a matching snapshot that arrived in the read/write interval without weakening replacement guards.
- Before a subscription-only cache merge, compare Plan, ChatGPT account, email and workspace identity from the returned summary to the current cached summary. Reject older successful-check or credential-refresh timestamps, including missing incoming timestamps when the current value is known. Compare workspace labels only when workspace IDs are absent. Alias, policy, health and quota changes do not invalidate the source.
- Keep cancellation of older in-flight list reads and pending mutation tracking unchanged. Later polls remain authoritative; rejected responses do not restore historical source data.
- Use controlled independent database sessions to save or replace data at the read/write boundary, then check public dashboard routes. Use deferred mutation responses against completed list reads to verify both rejection and successful subscription-only merges.

## Risks / Trade-offs

- Token persistence remains sensitive: retain the mandatory refresh-token CAS and test replacements between read and write as well as matching snapshots.
- Frontend source checks use public summary fields; raw credentials remain server-only. Credential freshness uses the existing lastRefreshAt timestamp.
- Missing historical timestamps fail conservatively when current timestamps are known; a subsequent authoritative poll can supply the current server result.

## Migration Plan

No additional migration or runtime edits. Validate tests, browser evidence, build and strict specs before archiving.
