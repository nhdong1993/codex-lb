## 1. Implementation and regressions

- [x] 1.1 Guard first-Free enqueue with pending evidence; verify delayed enqueue through account summary and PostgreSQL lock contention tests.
- [x] 1.2 Match the actual required owner before rejecting excluded bridge sessions; verify both routes and in-flight creation while retaining same-owner rejection coverage.
- [x] 1.3 Classify bridge evidence SQL failures as local admission errors; verify sanitized responses, reservation/gate cleanup and accepted sibling completion.

## 2. Integration and documentation

- [x] 2.1 Run relevant usage, routing and bridge suites, lint/type checks and proxy architecture guards; record results and remaining limitations.
- [x] 2.2 Sync requirements/context, pass strict OpenSpec validation, verify implementation against scenarios and archive the completed change.
