## Why

The fork still pins a Rustls release affected by RUSTSEC-2026-0285 and retains upstream defects in probing, credit eligibility, WebSocket drain admission, and code-less usage-limit terminals. Selected fixes can be incorporated without the non-rolling-safe beta.9/beta.10 schema removals or replacement of fork functionality.

## What Changes

- Upgrade the locked Rustls/AWS-LC dependency family and packaging assertions from upstream #2453/#2454.
- Omit the unsupported Force Probe output-token field (#2496).
- Require unlimited credits or a positive spendable balance for credit-backed quota overrides (#2119).
- Reject new WebSocket upgrades during drain with retryable HTTP 503 and Retry-After (#2255).
- Recognize upstream code-less usage-limit terminal messages consistently in HTTP/WebSocket retry, health, and refresh gates (#2449), preserving settlement and ownership invariants.
- Preserve existing uncommitted work, including message-qualified server-error isolation, new-account warmup, source WebSocket routing, and dashboard changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `outbound-http-clients`: patched native TLS dependency family.
- `usage-refresh-policy`: probe request compatibility, spendable-credit evidence, and message-based usage refresh.
- `graceful-shutdown`: retryable WebSocket drain denial.
- `account-routing`: message-qualified usage-limit terminal handling independent of delivery form.

## Impact

Rust manifests/lockfile, account probe, shared quota logic, admission middleware, proxy error predicates and their consumers, regression tests, and OpenSpec. No migrations, new settings, UI changes, full release merge, commit, push, or production deployment are included. The existing fork schema and custom source ownership remain intact.
