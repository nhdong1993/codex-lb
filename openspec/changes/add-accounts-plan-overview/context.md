# Context: Accounts plan overview

## Purpose

The Accounts page is a list/detail workbench: one tall card per account. At 200+ accounts the operator scrolls to answer simple questions such as "how many Plus accounts are rate limited?" or "how much weekly quota is left on Pro?". The overview answers those from one screen.

The idea comes from a three-tile summary (status, 5-hour quota, weekly quota) on another relay dashboard that draws one dot or column per account. That form stops being readable past a few dozen accounts, so this page groups accounts by plan and bins quota into ten buckets: the number of marks depends on plans and windows, not on account count.

## Decisions

- **Sub-route, not a nav item.** The core navigation is at its budget (`.github/simplicity-budgets.toml`). `routePermission` matches `/accounts/` by prefix, so `/accounts/overview` inherits `accounts:read` without new guard code.
- **Remaining percent.** The rest of the dashboard reports remaining quota and colors it with `quotaBarColor`; the overview follows suit.
- **Raw plan types.** `prolite` stays separate from `pro` (display requirement in `usage-refresh-policy`; capacities differ).
- **Average per account.** Inside one plan every account has the same capacity, so the per-account average equals the plan's remaining capacity share. Across plans it does not, so the all-plans row labels its figure as an average per account. Pool-wide credit capacity already appears in the dashboard donuts.
- **Separate windows.** Monthly quota is its own tile, never merged into 5-hour or weekly. A window appears when any account in the group reports a percentage or a window length.
- **Missing data.** A `null` percentage is excluded, never counted as zero. A window with no known values shows "–".
- **"Active" wording.** Active is the stored status, not a promise that routing will pick the account (cooldowns, thresholds, and model compatibility still apply).

## Constraints and failure modes

- Data comes from the existing `["accounts", "list"]` query (30-second polling, shared with the header), so the page adds no request load.
- Unknown status values follow `normalizeStatus` and count as active, as everywhere else in the dashboard.
- Each histogram scales to its own tallest bucket; the caption states that bucket's count, each bar shows its count on hover, and the histogram's accessible description lists every bucket's count.
- Figures are recomputed on every render (each poll re-renders the page), not memoized on the response, so the next reset moves past elapsed resets even when a poll returns identical data.

## Example

Three Plus accounts at 5-hour remaining 100, 45, and `null`:
- 5-hour tile: "72.5%" average, "2/3 with data", bars in buckets 90–100 and 40–50, zero accounts below 10%.
