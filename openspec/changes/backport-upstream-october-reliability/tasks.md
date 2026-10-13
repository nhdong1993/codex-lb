## 1. Backport the approved fixes

- [x] 1.1 Upgrade only the Rustls/AWS-LC dependency family and packaging assertions from #2453/#2454; verify a locked native build and tests.
- [x] 1.2 Port Force Probe payload compatibility (#2496) with service and dashboard-route regression tests, preserving warmup edits.
- [x] 1.3 Port spendable-credit eligibility (#2119) with mapper, selection, and multi-replica coverage; retain quota precedence and disabled states.
- [x] 1.4 Port retryable WebSocket drain denial (#2255), testing both route families, non-proxy paths, and admitted-connection cleanup.
- [x] 1.5 Port code-less usage-limit recognition (#2449) across HTTP and WebSocket health/retry/refresh paths, preserving fork isolation, source ownership, and settlement ordering.

## 2. Verify and hand off

- [x] 2.1 Run focused and mapped regression suites, static checks, and native transport/packaging checks with isolated synthetic data; record exact results and limitations.
- [x] 2.2 Synchronize delta specs and stable context without overwriting unrelated changes, validate OpenSpec strictly, and review task-only diffs.
- [ ] 2.3 Verify requirement coverage, record preservation evidence, and archive the verified change without commit, push, or deploy.

Requirement coverage and preservation verification are recorded in `verification.md`. The archive checkpoint remains open pending confirmation and disposition of the intermittent full-file WebSocket teardown timeout; targeted regressions pass.
