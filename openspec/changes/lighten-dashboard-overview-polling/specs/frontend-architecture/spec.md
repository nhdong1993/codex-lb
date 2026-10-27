## ADDED Requirements

### Requirement: Dashboard overview weekly pace opt-out

`GET /api/dashboard/overview` SHALL accept a boolean `weeklyPace` query parameter that defaults to `true`. When it is `false`, the response SHALL carry `weeklyCreditPace: null` and the server MUST NOT load usage history or API-key attribution for the weekly credit pace; every other field SHALL match the default response.

#### Scenario: Overview without weekly pace
- **WHEN** a client requests `GET /api/dashboard/overview?timeframe=7d&weeklyPace=false` for a pool with weekly usage
- **THEN** `weeklyCreditPace` is `null` and the accounts, summary, windows, and trends match the default response

#### Scenario: Default keeps weekly pace
- **WHEN** a client requests `GET /api/dashboard/overview?timeframe=7d` for a pool with weekly usage
- **THEN** `weeklyCreditPace` is populated

### Requirement: Overview and status bar skip weekly pace

The Overview page and the status bar SHALL request the dashboard overview with `weeklyPace=false` through one cached query per timeframe, separate from the Dashboard page's query, and SHALL poll it every 60 seconds whatever the dashboard refresh interval.

#### Scenario: Default refresh interval
- **WHEN** the dashboard refresh interval is 15 seconds and the Overview is open
- **THEN** the overview request carries `weeklyPace=false` and repeats every 60 seconds
