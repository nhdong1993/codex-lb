# Account quota presentation context

The [requirements](spec.md) keep Free monthly quota distinct from paid short/weekly windows and preserve quota display continuity during refreshes.

## Monthly sorting

The Accounts List includes a Monthly control in the labeled desktop Sort quota group and ascending/descending options in the shared sort dropdown, including on mobile. The Quota remaining heading describes the data region regardless of whether rows show one Monthly bar or paired paid quota windows. They use raw monthly remaining percentages; sorting does not depend on animated display values or the selected 5h/Weekly appearance preference. No extra API request is needed.

For example, filter Plan to Free and choose Monthly lowest remaining: accounts with 0%, 25% and 90% appear in that order, followed by accounts whose monthly quota is unknown. Reverse the direction to prioritize the largest remaining monthly quota. Paid accounts without monthly data stay last when the list is mixed.

Unknown quota is distinct from exhaustion. Monthly-only rows keep a single Monthly bar; they do not copy that value into a 5h or 7d slot. Temporary unknown values can retain the last visible percentage under the existing smoothing policy, while sorting continues to use the raw snapshot. Existing reset-time sorting is unchanged.
