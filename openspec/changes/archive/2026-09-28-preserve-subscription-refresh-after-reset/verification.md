# Verification

- `bun run test -- src/features/accounts/hooks/use-accounts.test.ts` — 28 tests passed.
- `bun run typecheck` — passed.
- `bun run lint -- src/features/accounts/subscription-refresh.ts src/features/accounts/reset-reconciliation.ts src/features/accounts/hooks/use-accounts.ts src/features/accounts/hooks/use-accounts.test.ts` — passed.
- `bun run build --outDir /tmp/codex-lb-subscription-reset-fix-build` — passed.
- `bun run screenshots account-grid.spec.ts` — 5 browser tests passed.
- `npx --yes @fission-ai/openspec validate preserve-subscription-refresh-after-reset --strict` — passed.
- `npx --yes @fission-ai/openspec validate --specs --strict` — 66 specs passed.

The regression covers a reset summary held in flight while a subscription refresh returns. It asserts that the quota summary is applied, the newer subscription deadline remains in both account and dashboard projections, and a subsequent poll does not regress it.
