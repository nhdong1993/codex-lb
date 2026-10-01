# Design

## Context

The previous change uses three mobile grid tracks for nowrap badges and three content-width quota header buttons above one or two quota bars. Review demonstrated badge intersections at 320px and a 119px offset between the 7d header and its data at 1440px.

## Decisions

- Put Plan, Status and Reset in a wrapping flex group on mobile. Use `display: contents` on desktop so the existing shared header/row grid continues to position them as separate columns. Prevent each metadata cell from shrinking below its badge width.
- Move the existing quota sort buttons into a labeled `Sort quota` group above the List headers; label the quota column `Quota remaining`. This avoids empty synthetic quota columns for monthly-only accounts and remains accurate for mixed fleets and 5h/Weekly display preferences.
- Keep the same sort modes, direction indications, mobile dropdown and reset badge setting. No account request or action semantics change.

## Constraints and edge cases

At 320px a long status can move the reset count onto a second line. The row may grow to accommodate readable content; preserve the existing 180px limit at 390px and the 80px desktop limit. Test English, Korean and Chinese badge intersections, not just document scroll width.

## Example

An Enterprise account marked Re-auth required with Reset (12) wraps at 320px without overlapping. In a mixed Plus/Free list, the shared Quota remaining heading covers paired 5h/Weekly bars or one Monthly bar. Monthly sorting remains available in the separate sort group and dropdown.
