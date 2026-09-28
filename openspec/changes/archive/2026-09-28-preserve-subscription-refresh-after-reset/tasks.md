# Tasks

## 1. Merge subscription and reset snapshots

- [x] 1.1 Add a compatibility-aware account snapshot merge helper and use it from reset reconciliation; verify identity mismatches and newer inactive results are not overwritten.
- [x] 1.2 Synchronize merged subscription refreshes into list/dashboard caches and reset reconciliation state; verify later polls cannot restore the older term.

## 2. Regression coverage

- [x] 2.1 Add a public `useAccounts` regression test for a delayed reset summary after a successful subscription refresh, asserting both quota and subscription fields.
- [x] 2.2 Run the focused frontend account tests and type/lint/build checks; record results in verification.md.
