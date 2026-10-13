# Verification

## Completeness

All tasks are complete. Three new requirements and their scenarios are synced to frontend-architecture/spec.md, with stable context in context.md.

## Correctness

- Component tests: 54 tests across API List (8), APIs page (7), API detail (15), overview (2) and edit dialog (22) passed across focused runs. A lazy edit-dialog assertion timed out during a concurrent build; its focused rerun and final full page suite passed.
- Playwright: 3 language scenarios passed on the production build. Covers 1440/1024/390/320px, row heights, no page overflow, unused filtering, row keyboard activation, nested edit dialog, reachable mobile Close, view switching, persisted List preference and request sorting.
- TypeScript and Vite build passed. Scoped ESLint and git diff --check passed.
- Strict change validation passed. All 67 main specifications passed strict validation.

## Coherence and scope

Detail remains the default, and a single ApiList owns search/filter/sort state through view changes. Shared quota presentation retains the sidebar's existing capacity/unknown rules. List does not expose secret keys or add requests per row; selected-detail queries are gated by visibility. Used/Idle overview counts and the filter share the same predicate. Missing request summaries sort after known zero/positive counts in both directions.

Browser verification found the existing edit dialog exceeded the phone viewport, so this change bounds its height and makes it scrollable. Browser regression coverage confirms Close is reachable. The screenshot harness serves the built index for /apis because Vite's /api proxy prefix also matches /apis; production routing was not changed.

## Evidence

Before images were captured from an isolated frontend export of HEAD, with synthetic fixtures. After images use synthetic fixtures with both used and unused keys.

- [Original desktop](evidence/before/desktop.png) / [List desktop](evidence/after/list-en-1440.png)
- [Original phone](evidence/before/mobile.png) / [List phone](evidence/after/list-en-320.png)
- [Preserved Detail view](evidence/after/detail-desktop.png)
- [Korean phone](evidence/after/list-ko-320.png) / [Chinese phone](evidence/after/list-zh-CN-320.png)

All checks passed; ready for archive. No API List commit, push or deployment performed.
