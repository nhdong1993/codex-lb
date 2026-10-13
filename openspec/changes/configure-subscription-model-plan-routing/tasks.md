## 1. Preparation

- [x] Record scope and acceptance scenarios; read project conventions and architect findings.
- [x] Capture dirty baseline and continue the existing OpenSpec change before behavior edits.

## 2. Implementation

- [x] Add settings persistence, migration, validation, serialization and partial PUT semantics.
- [x] Apply policy to subscription selection, caches, retries and warm admission without changing owners.
- [x] Add native-model/plan editor under routing settings, including saved absent models.
- [x] Integrate and verify the concurrent direct native HTTP final-send/same-account retry correction (2026-10-13 integration run in verification.md).

## 3. Author verification and documentation integration

- [x] Cover settings, product routing, source isolation, strict owners, retries and warm lifecycle.
- [x] Verify isolated SQLite migration upgrade/backfill, downgrade/re-upgrade and single head.
- [x] Run scoped backend/frontend format, lint, type checks and tests; capture screenshots.
- [x] Validate final change strictly and synced main specs nonstrictly; record exact evidence and limitations in verification.md.
- [x] Sync author-verified normative requirements and stable context to main specs before independent review of the combined diff.

Counts overlap; these author checks are not independent approval. Baseline
failures and unvalidated environments remain documented in [verification.md](verification.md).

## 4. Independent gates (not author approval)

- [ ] Independent non-author reviewer verifies the final task-only diff, screenshots, both synced capabilities and applicable gates.
- [ ] Archive only after independent verification (not in this worker).

## Post-deployment operator note — unapplied, not a verification gate

After a separately authorized deployment, an operator may PUT the three-model
Free example in [context.md](context.md#example-and-post-deployment-operational-note--not-applied)
using the supported settings API. The mapping is not a seeded default and has
not been applied. No deployment or live settings change is authorized here.
