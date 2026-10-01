# Verification

## Checks

- Focused Vitest run: `account-list-sorting.test.tsx`, `account-list-overview-row.test.tsx`, `account-list.test.tsx`, `accounts-page.test.tsx`, `sorting.test.ts` — 48 tests passed.
- Frontend ESLint (`bun run lint --` with affected paths; the script also lints the full frontend) — passed.
- TypeScript and Vite production build (invoked by Playwright webServer) — passed after correcting a test-only Testing Library option.
- Before-change List browser baseline — passed and captured.
- Browser suite: subscription response/race checks, Detail and Grid responsive scenarios passed. The List scenario detected 188px mobile rows; spacing was reduced without relaxing the existing 180px bound.
- Final affected browser run: `bun run screenshots account-grid.spec.ts -g 'List separates|Accounts list overview'` — both tests passed. Covers headers and mobile dropdown, Status/Reset direction, unknown and zero counts, mixed and filtered Free quota, 1024/1440px column alignment, disabled reset badges, and desktop/mobile row height/overflow. Existing List checks also cover 768px, management, Burn First, subscription refresh, and view switching.
- Strict change validation — passed.
- `openspec validate --specs --strict` — 67 specifications passed, zero failures.
- `git diff --check` — passed.

## Requirement review

All four delta requirement blocks are implemented. Shared sorting retains pagination/filter/selection behavior; header controls use the same sort modes as the mobile menu. Reset counts have their own optional column and preserve expiry tie-breaking. Monthly sorting uses raw monthly percentages, leaves unavailable windows last and preserves monthly-only rendering. No API requests, credentials, migrations or runtime state were changed.

## Screenshots

- Desktop [before](evidence/before/list-desktop.png) / [after](evidence/after/list-desktop.png)
- Mobile [before](evidence/before/list-mobile.png) / [after](evidence/after/list-mobile.png)
- [Mixed plans at 1024px](evidence/after/list-mixed-1024.png)
- Free Monthly sorting: [desktop](evidence/after/list-free-desktop.png) / [mobile](evidence/after/list-free-mobile.png)
- [Dark mode](evidence/after/list-desktop-dark.png)
- [Reset column hidden](evidence/after/list-without-reset-desktop.png)

Images use synthetic browser fixtures. Main specifications and context documents are synchronized. This change was verified locally; no deployment was performed.
