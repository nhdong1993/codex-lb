## 1. Proxy and clients

- [x] 1.1 Retire a denied proxy-injected WebSocket anchor instead of re-injecting it (`6b3d031e`, #2248), with a WebSocket route regression.
- [x] 1.2 Bound the aggregate detached-retirement lock wait (`09b8e891`, #2315).
- [x] 1.3 Route anonymous output frames to the created response (`976d20b7`, #2357).
- [x] 1.4 Reuse system trust for Python WSS (`bb98cdf4`, #2110).
- [x] 1.5 Skip unused HTTP preparation serialization (`ff6f6a17`, #2113), with the fork's settings-based budget in its test.

## 2. Warm-up

- [ ] 2.1 Warm unused Free quota once (`a7785a80`, #2205), with a background-repository guard test and the routing doc sentence.

## 3. Dashboard reads

- [ ] 3.1 Bound the conversation presence raw tail (`a408b57a`, #2235).
- [ ] 3.2 Memoize the trailing-demand aggregate (`913c6eb5`, #2236).

## 4. UI

- [ ] 4.1 Offer Resume for deactivated accounts (`0f6a31c5`, #2060), with before/after screenshots and the browser smoke suite.
- [ ] 4.2 Preserve quota chart samples and per-account display state (`ec994599`, #2489), with before/after screenshots.

## 5. Planner and routing

- [ ] 5.1 Validate quota planner timezones (`a3aa8caa`, #2468).
- [ ] 5.2 Reject invalid planner clock times (`6ed4c44f`, #2540).
- [ ] 5.3 Build background account states from the dashboard snapshot (`6cdf29ef`, #2233), keeping `load_balancer_lines` at 3021.

## 6. Verify and hand off

- [ ] 6.1 Run the global gates and end-to-end scenarios; record results and limitations in `verification.md`.
- [ ] 6.2 Sync delta specs and stable context into canonical specs; validate strictly and check block equality.
- [ ] 6.3 Archive the change after the operator accepts and requests it.
