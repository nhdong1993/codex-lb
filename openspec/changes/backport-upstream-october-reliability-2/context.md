## Scope and rationale

Round 2 of the selective upstream backport. The sources are upstream commits from `origin/main` (`72630bbf`):

| Group | Upstream | Fork commit purpose |
| --- | --- | --- |
| A | `ed487558` (#2622) | rustls 0.23.46 (RUSTSEC-2026-0346 Debug secret exposure, -0347 ECH buffered data, -0348 Brotli 1 GiB allocation, -0349 ServerHello KEX downgrade) |
| A | `0b294950` (#2588) + floor of `a563790a` (#2595) | urllib3 2.8.0 (CVE-2026-97687, CVE-2026-97689) |
| A | `2a241401` (#2407) | upgrade `gzip`, `libpcre2-8-0`, `libsqlite3-0`, `perl-base` in the runtime image |
| C | `13ddf396` (#2528) + fork | GPT-6 128000 output fallback, including `gpt-6.1-sol` |
| C | fork | fallback Codex client version 0.163.0 |
| C | `402c2f51` (#2517) | `codex_cli_rs` → `codex-cli` telemetry family |
| C | `d617212a` (#2525) tests | base-instruction edge cases (code already in the fork from `00164ab0`) |
| B | `c62bdd80` (#2362), `f94dd509` (#2427), `fbb97519` (#2545), `e4bc88ff` (#2524) | worker stop, shared-future exceptions, retained invalidations, probe snapshot |
| B | `3d501ac5` (#2405) | rate-limited recovery on any confirmed window reset |
| B | `81b9fbd5` (#2234), `2c853992` (#2381) | soft-owner spillover; excluded hard owner |
| B | `98d2256d` (#2353), `9db05a1b` (#2083) | bridge reservation reuse; model-transition fork |
| B | `b28d9afc` (#2131), `3d8fa7ba` (#2573) | safety-block neutrality; deactivated workspace |
| B | `d1fd2f21` (#2111), `6b10052e` (#2469) | early owner publication; typed file failover provenance |

Not taken: `7f792970` (#2360) and `e54d9743` (#2408), which contradict fork policy; `cb21daae` (#2386), deferred; the four `chore(metadata)` pricing refreshes, which edit files from the absent #2298 feature and introduce no price disagreement for any model the fork prices.

## Constraints and preservation

The following fork behaviors must survive:

- Narrow processing-error isolation (`overload_backoff.py`).
- The first-trip soft-owner rebind (`614cf5c2`).
- Capacity replay and its prelude hold (`238a6488`, `9130618d`).
- Plan-policy model admission (`16ff01d7`).
- Reauth quarantine (`3f4b03a6`).
- Reset-credit redemption and new-account warm-up.
- Source routing: no account selection, admission lease or account-health write, while the existing API-key reservation and settlement are kept.
- Round 1 code-less usage-limit handling and settlement-first health.

Upstream OpenSpec change folders and canonical spec hunks are not imported verbatim. Each requirement here was checked against the fork's canonical text, which equalled upstream's pre-commit text in every case except `model-catalog-compat`. That one is adapted to the fork's override wording, which has no dashboard row.

## Failure examples

- **Deactivated workspace after refresh:**
  - Example: an API-key request gets 401, the token refresh succeeds, and the redispatch gets HTTP 402 `deactivated_workspace` on a file-pinned owner.
  - Before: the account health write could run while the key's reservation was still open.
  - After: the reservation is closed first, then the account becomes `deactivated`, with no sibling dispatch.
- **Bridge replay spin:** a created-only bridge replay whose hard owner is in the request's own exclusions re-selected every 2 s until the 7200 s budget ran out. Now it fails at once.
- **Soft owner moved by one transient failure:** a single output-free capacity terminal moved a prompt-cache thread to a sibling forever. Now the sibling serves only that turn, unless the owner is in sustained backoff or rejected by model admission.
- **Safety block penalized the account:** `misalignment_policy_violation` "This request was blocked by our safety systems." counted as an account error. It is now account-neutral; `cyber_policy` still routes as before.
- **Early reset ignored:** a Plus account was benched on a 5h window until its predicted `reset_at`, although refreshed usage showed the window had reset (for example after a reset-credit redemption). It now recovers when exactly one window's reset matches the stored deadline.
- **Capacity replay and early publication:** the first account sends `response.created` (`resp_x`) and then an output-free capacity `response.failed` (`resp_x`); the request is replayed on another account. `resp_x` is never published as an owner.
- **Cold fallback version:** with GitHub unreachable at startup, the old `0.153.4` fallback presented a version below gpt-6-luna's `0.155.0`, and the catalog dropped that model. `0.163.0` matches the live value.

## Operations

- All validation uses synthetic data on this host:
  - pytest runs serially from the fix worktree with the main venv;
  - `CODEX_LB_TEST_DATABASE_URL` and `CODEX_LB_DATABASE_URL` are unset, so a temporary SQLite DB is used;
  - the env file is empty.
- The native helper is built and tested in a disposable `rust:1.96.0-slim-bookworm` container limited to 2 CPUs.
- The full CI matrix, the full image build and Python 3.14 product-path tests are not run here.
- Merge, push and HA deployment need separate operator requests. After deployment, check `python -c "import urllib3; print(urllib3.__version__)"` in a backend container (expected `2.8.0`).
