## 1. Security and dependencies (A)

- [x] 1.1 Bump rustls to 0.23.46 (`ed487558`); build and test the native helper in a disposable container and run the native wire suites.
- [x] 1.2 Require and lock urllib3 2.8.0 (`0b294950`, floor of `a563790a`), keeping the package version.
- [x] 1.3 Upgrade the remaining high-severity Debian runtime packages (`2a241401`).

## 2. Model metadata (C)

- [x] 2.1 Advertise GPT-6 max output tokens, including `gpt-6.1-sol` (`13ddf396`).
- [ ] 2.2 Raise the fallback Codex client version to 0.163.0, with a bootstrap-floor invariant test.
- [ ] 2.3 Map the `codex_cli_rs` user agent to the `codex-cli` family (`402c2f51`).
- [ ] 2.4 Port the base-instruction edge-case tests only (`d617212a`).

## 3. Reliability fixes (B)

- [ ] 3.1 Let the deletion scheduler exit its wait promptly (`c62bdd80`).
- [ ] 3.2 Consume a shared future's exception when no waiter is left (`f94dd509`).
- [ ] 3.3 Retain failed immediate invalidations (`fbb97519`).
- [ ] 3.4 Snapshot force-probe state before session cleanup (`e4bc88ff`).
- [ ] 3.5 Recover a rate-limited account on any confirmed window reset (`3d501ac5`).
- [ ] 3.6 Keep a soft sticky owner that is only request-locally unavailable (`81b9fbd5`).
- [ ] 3.7 Stop waiting on a hard affinity owner the caller excluded (`2c853992`).
- [ ] 3.8 Reuse the reservation during local bridge recovery (`98d2256d`).
- [ ] 3.9 Fork model-transition owner conflicts (`9db05a1b`).
- [ ] 3.10 Keep safety-policy blocks account-neutral on HTTP, WebSocket and bridge (`b28d9afc`).
- [ ] 3.11 Exclude deactivated workspaces and fail over safely, settling before health on both terminal sites (`3d8fa7ba`).
- [ ] 3.12 Publish HTTP response owners before delivery, never for capacity-replayed attempts (`d1fd2f21`).
- [ ] 3.13 Preserve routed file failover provenance (`6b10052e`).
- [ ] 3.14 Confirm source routing stays account-neutral and keeps its key reservations.

## 4. Verify and hand off

- [ ] 4.1 Run the global gates and end-to-end scenarios; record results and limitations in `verification.md`.
- [ ] 4.2 Sync delta specs and stable context into canonical specs; validate strictly.
- [ ] 4.3 Archive the change after the operator accepts and requests it.
