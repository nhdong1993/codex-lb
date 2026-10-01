# Design

## Context

See [proposal.md](proposal.md). Account summaries already contain all required values; List has shared sorting before filtering/pagination and a mobile sort menu.

## Goals / Non-Goals

Keep the existing default reset-credit priority and compact desktop rows. No upstream refresh, schema change, reset redemption action, or changes to Detail/Grid layout are needed.

## Decisions

- Reuse the sorting union and header controls. Status uses a fixed operational order, with menu labels describing active-first/inactive-first; localized text sorting would make ordering inconsistent between languages.
- Make Reset a separate optional column. Its badge displays zero; missing counts use an em dash and sort last. The existing most-reset-credits option is equivalent to descending Reset and retains expiry tie-breaking.
- Reuse the quota group for a Monthly header control and its existing single monthly-only bar. This avoids empty synthetic paid quota bars and keeps mixed-plan rows short.
- Monthly sorting reads raw percentages, not animated or held display values. Existing reset-time sort behavior is outside this change.
- Share desktop grid widths between header and rows, with a variant when the Reset column is hidden. Mobile uses labeled compact cells and the existing dropdown.

## Risks / Trade-offs

- Extra columns crowd laptop widths: verify at 1024px, 1440px and mobile widths with long status text.
- Unknown versus zero can reorder the default list: use known counts first and retain deterministic expiry/name/id tie-breakers.

## Example and verification

Filter Plan to Free, choose Monthly lowest remaining, and expect 0%, 25%, 90%, then unknown. Clicking Status or Reset headers toggles direction, resets pagination and keeps the selected account. Verify component behavior and browser screenshots before/after, including reset badges disabled.
