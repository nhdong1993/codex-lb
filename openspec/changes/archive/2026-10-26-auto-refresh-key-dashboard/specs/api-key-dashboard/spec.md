## ADDED Requirements

### Requirement: Automatic refresh of the active key dashboard tab

While connected, the key dashboard SHALL refresh the data of the active Overview or Group keys tab every 30 seconds while the browser document is visible, and SHALL refresh it once when the document becomes visible again. It MUST NOT refresh while the document is hidden and MUST NOT refresh the Install tab automatically.

Automatic refreshes MUST NOT show a loading indicator or clear displayed data. A non-401 failure MUST keep the displayed data and show an error alert that is removed after the next successful refresh; a 401 MUST disconnect as defined for other key-dashboard requests. An automatic refresh MUST NOT start while a request of the same tab is pending and MUST NOT abort a pending request. A manual Refresh, request-log page change, or connect MUST still run, and the response of a superseded automatic refresh MUST be discarded.

On Overview, every automatic refresh SHALL reload the profile and usage; it SHALL reload request logs only while the first log page is displayed and MUST keep a later page unchanged. On Group keys, automatic refreshes MUST keep the selected chart metric, the open daily table, and each member's visibility, identifying members by name and masked prefix rather than position.

#### Scenario: Refresh the visible Overview

- **WHEN** a connected holder keeps Overview open on the first log page for 30 seconds in a visible browser tab
- **THEN** the profile, usage, and request logs are requested again with the same in-memory key
- **AND** the new values replace the old ones without a loading indicator

#### Scenario: Pause while hidden

- **WHEN** the browser tab is hidden for longer than 30 seconds and then becomes visible
- **THEN** no key-dashboard request is sent while hidden
- **AND** exactly one refresh of the active tab starts when it becomes visible

#### Scenario: Keep a later log page

- **WHEN** the holder views the second request-log page and an automatic refresh runs
- **THEN** usage and profile are refreshed
- **AND** request logs are not requested and the displayed page is unchanged

#### Scenario: Background failure

- **WHEN** an automatic refresh fails with a server error
- **THEN** the previously displayed data remains with an error alert
- **AND** the alert disappears after the next successful refresh
- **AND** a 401 instead returns to the API key entry screen and removes any remembered key

#### Scenario: Refresh group usage without losing chart choices

- **WHEN** a holder hides a member in the daily chart and an automatic refresh returns the members in a different order
- **THEN** the refreshed totals are displayed and the same member stays hidden

#### Scenario: No overlap and no Install refresh

- **WHEN** a tab's request is still pending at the next 30-second tick
- **THEN** no second automatic request starts and the pending request is not aborted
- **AND** a manual Refresh during a pending automatic Overview refresh shows the manual response
- **AND** while Install is open no profile, usage, log, group, or installer request is sent automatically
