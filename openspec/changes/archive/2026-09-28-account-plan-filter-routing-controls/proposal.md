## Why

Operators need to narrow the Accounts view by plan and change Burn First without opening each account. Plan labels should also be visually consistent with the dashboard request log, including the newer Prolite and Promax plans. Subscription checks can run once per day, while operators still need an explicit way to refresh a selected account immediately.

## What Changes

- Add a plan filter shared by Detail, List and Grid account views.
- Add a quick Burn First toggle to List rows.
- Reuse dashboard request-log plan badge styling for account views and add distinct Prolite and Promax styles.
- Reduce automatic subscription refresh frequency to once per account per day and add a write-protected manual refresh action.

## Impact

Dashboard account controls, subscription refresh API/scheduler, frontend translations and tests. No new account fields or operator settings are required.
