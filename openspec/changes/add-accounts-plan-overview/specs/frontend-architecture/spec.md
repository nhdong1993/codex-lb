## ADDED Requirements

### Requirement: Accounts overview route and tabs

The dashboard SHALL serve a read-only Accounts overview at `/accounts/overview` under the same `accounts:read` guard as `/accounts`, without adding a core navigation item. Both routes SHALL show "List" and "Overview" tabs that link to each other, and only the tab for the current route SHALL carry `aria-current="page"`.

#### Scenario: Operator opens the overview
- **WHEN** an operator with `accounts:read` selects the Overview tab on the Accounts page
- **THEN** the URL becomes `/accounts/overview` and only the Overview tab is current

#### Scenario: Session without accounts access
- **WHEN** a session without `accounts:read` opens `/accounts/overview` directly
- **THEN** the dashboard redirects to `/dashboard`

### Requirement: Accounts overview groups accounts by plan

The overview SHALL build its figures from the accounts list response. It SHALL show one row for all accounts first, then one row per raw plan type ordered by account count descending and then by plan name, keeping `prolite` separate from `pro`. Each row SHALL show its active accounts over its total and a count per status.

#### Scenario: Rows by plan
- **WHEN** the pool has three Plus accounts, one Pro account, and one Pro Lite account
- **THEN** the all-plans row comes first, then Plus, then Pro and Pro Lite as separate rows

#### Scenario: Status counts
- **WHEN** a plan has two active accounts and one rate-limited account
- **THEN** its row shows 2 of 3 active and one rate-limited account

### Requirement: Accounts overview quota windows

Each overview row SHALL show one tile per quota window (5-hour, weekly, monthly) that any of its accounts reports through a remaining percentage or a window length, and SHALL never merge monthly into another window.

#### Scenario: Monthly-only plan
- **WHEN** every account of a plan reports only a monthly window
- **THEN** that plan's row shows a monthly tile and no 5-hour or weekly tile

#### Scenario: Window without data
- **WHEN** a plan reports a weekly window length but no account has a weekly percentage
- **THEN** the weekly tile shows no average and zero accounts with data

### Requirement: Accounts overview quota tile figures

A quota tile SHALL show the average remaining percentage per account over known values, the count of accounts with a known value, the count below 10 percent, the next future reset, and a ten-bucket histogram of remaining percentage with an accessible text summary. A missing percentage SHALL be excluded, not counted as zero.

#### Scenario: Missing and boundary values
- **WHEN** a plan has accounts with 5-hour remaining 100, 9.9, and no value
- **THEN** the 5-hour tile averages 54.95 percent over 2 accounts with data, counts 1 account below 10 percent, and places 100 in the 90–100 bucket
