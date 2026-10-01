# Design

## Context

List already receives `availableResetCredits` and `resetCreditNearestExpiresAt`. The Accounts page has a shared minute clock for subscription labels. See proposal.md for motivation.

## Goals / Non-Goals

Keep the existing compact Reset cell and its row-selection behavior. Scope this indicator to Accounts List; do not change redemption or notification settings.

## Decisions

- Reuse the nearest-expiry summary and compare raw milliseconds against an inclusive 72-hour boundary. Do not round day counts, which would include almost-four-day credits.
- Extract shared clock access into a small hook so the dot and subscription labels use the existing single timer. No new per-row polling or API calls.
- Position an 8px red dot above the badge using a relative wrapper and absolute positioning. Keep it outside the badge's overflow clipping and let pointer events reach the row button.
- Use localized accessible text so color is not the only description of the warning.

## Risks / Trade-offs

- Summary snapshots can be stale; only positive counts with valid, still-future expiries qualify. Expired snapshots do not show the warning.
- The shared clock updates once per minute; test both boundary transitions with a fixed clock.
- Small phone layouts can clip decorations; check the dot bounds and row selection in a browser at 320px and desktop widths.
