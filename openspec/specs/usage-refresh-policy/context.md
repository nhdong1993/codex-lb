# Usage Refresh Policy Context

## Purpose

This context explains how codex-lb derives an account's usage and status, and
how to diagnose disagreements between codex-lb and Codex Desktop or the Codex
CLI quota pill.

codex-lb treats `/wham/usage` as the source of truth for account usage. Other
OpenAI account surfaces can display reset state earlier than `/wham/usage`,
especially during team reset windows, so the dashboard can temporarily show an
account as `rate_limited` even when Codex Desktop says the quota has reset.

## Access and refresh eligibility

A permanent refresh-token failure marks an account `reauth_required` and stops
proactive exchange of that refresh material, while ordinary requests may keep
using the stored access token until its known expiry. Claimless forced refresh
first reads current state: it adopts genuine peer rotation, uses fresh ciphertext
as the guard for unchanged non-terminal material, and fails closed without
exchange when terminal material is unchanged. Before access-token expiry, a
request that reaches this terminal failure may fail over after excluding the
account locally; it does not globally de-route it or move owner-bound continuity
to another account. At known expiry, selection and bridge reuse reject the
account before upstream I/O.

## Upstream Usage Source

codex-lb refreshes account usage by calling:

```http
GET https://chatgpt.com/backend-api/wham/usage
```

The call is made per account on the configured refresh tick, which defaults to
60 seconds. The client lives in
[`app/core/clients/usage.py`](../../../app/core/clients/usage.py), and the
scheduler lives in
[`app/core/usage/refresh_scheduler.py`](../../../app/core/usage/refresh_scheduler.py).

## Status Derivation

The fetched usage is fed through
[`apply_usage_quota`](../../../app/core/usage/quota.py), which derives account
status from `primary_window.used_percent`:

- `secondary_used >= 100`, regardless of `primary_used`: `QUOTA_EXCEEDED`
- `used_percent >= 100` on the primary rate-limit window: `RATE_LIMITED`
- `used_percent < 100`: `ACTIVE`

There is no manual reset step inside codex-lb. Recovery is driven by the next
refresh tick that observes a sub-100 value from `/wham/usage`.

## Why Codex Settings Can Disagree

Codex Desktop's Settings -> Account view and `/wham/usage` are fed by different
OpenAI-side data sources:

- `/wham/usage` exposes the rate limiter's internal counter. It updates lazily,
  typically on the next chargeable request through that account, or when its
  internal window crosses `reset_at`.
- Settings -> Account is fed by a separate account/quota view that often picks
  up team-side reset events earlier.

During a reset window it is normal for Settings -> Account to show the reset
state while `/wham/usage` still returns `used_percent: 100` for a short period
afterwards. codex-lb mirrors `/wham/usage` during that window, so the account
stays `RATE_LIMITED` or `QUOTA_EXCEEDED` until upstream catches up.

## Limit Warm-Up Exhaustion Threshold

Reset-confirmed limit warm-up compares the usage sample from before a refresh
with the sample written after that refresh. The pre-refresh sample must be at
or above the configured exhausted threshold, the post-refresh sample must be
below `100`, and `reset_at` must move forward.

The exhausted threshold defaults to `99.0` because some upstream usage payloads
plateau at 99 percent for windows that are practically exhausted. This avoids
missing reset-confirmed warm-ups for those accounts while keeping the reset
confirmation requirement intact. Operators who want the historical strict
behavior can set the threshold to `100.0`.

## Operational Notes

- Wait first. The next request through that account usually wakes the upstream
  rate limiter; codex-lb auto-recovers on the next refresh tick after the
  upstream payload changes.
- The dashboard Force Probe action fires one minimal `responses.create` against
  the selected account and immediately refreshes its usage. The probe body uses
  `max_output_tokens=16` (the current Codex token floor); `1` is rejected
  upstream with HTTP 400 and never wakes the limiter. An accepted 2xx probe
  also contributes to that replica's probing-health recovery streak; non-2xx
  results do not restore routing health. Settlement reloads and normalizes
  weekly/monthly and zero-primary-capacity usage like ordinary routing and is
  discarded when newer replica-local runtime activity arrives during that
  snapshot load. This floor is the probe half of
  [#1895](https://github.com/Soju06/codex-lb/issues/1895); warmup/compact-404
  is a separate path.
- Do not manually flip the codex-lb account state to `ACTIVE` while
  `/wham/usage` still reports the account as fully used. That only masks the
  upstream state and can route traffic back to an account that the upstream
  limiter will reject.

## Verification Example

To confirm that the disagreement is upstream rather than codex-lb's mirror,
call `/wham/usage` directly with the same account token codex-lb is using:

```bash
ACCESS_TOKEN=...
ACCOUNT_ID=...   # chatgpt-account-id UUID, not codex-lb's id

curl -s https://chatgpt.com/backend-api/wham/usage \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "chatgpt-account-id: ${ACCOUNT_ID}" \
  -H "Accept: application/json" | jq '.rate_limit'
```

If `primary_window.used_percent` is still `100` here while Settings -> Account
shows the account as reset, codex-lb has nothing fresher to mirror. The account
is inside the upstream propagation window, and the practical fix is to wait or
use the Force Probe action. Check its `probe_status_code`: a non-2xx response
does not count as evidence that the account is healthy.

## Related Work

- [#676 - initial bug report on `/wham/usage` vs. Settings UI divergence](https://github.com/Soju06/codex-lb/issues/676)
- [#677 - dashboard per-account force-probe action](https://github.com/Soju06/codex-lb/issues/677)

## Priority confirmation of a suspected downgrade

The ordinary sequential fleet scan can leave a paid label visible long after upstream has downgraded the account. A first confirmable Free usage response, or the exact ChatGPT model-entitlement rejection, now requests shared priority verification. With background usage refresh enabled, a separate lifespan-owned scheduler polls every five seconds, claims up to three accounts and attempts subscription and usage checks independently. First-Free follow-ups become due after 15 seconds. Each request window permits three attempts within two minutes; duplicate errors share that budget. Slow upstream calls and a large simultaneous batch can delay completion beyond the usual 30–60 second target.

For example, a Plus account still showing an October 4 term reports Free on October 2. Its display switches to verification while the follow-up is pending. A second agreeing, correctly scoped usage sample persists Free. A recognized paid sample clears the suspicion; an unrecognized response retries within the budget. Subscription failures preserve the last successful snapshot, while explicit inactivity clears its deadline even if usage fails. Exhausted checks return to the existing fleet refresh policy.

Priority checks reuse the existing credential refresh path only after an actual usage authentication failure. Free confirmation itself does not rotate tokens or cause reauthentication. A permanent token failure can occur shortly after Free is confirmed; that ordering does not establish that the confirmation revoked the credential. Revoked credentials still require login/import, and this workflow cannot restore them. Replacement removes pending work atomically; generation and credential guards reject old responses. Routine successful token rotation preserves queued confirmation and existing observations.

### Contended replacement, new evidence and shutdown

PostgreSQL priority writes lock the account row before reading the credential or generation guard. This follows replacement's account-before-child lock order without holding locks during network requests. An INSERT SELECT guard alone is insufficient: its MVCC source can be read before waiting on a conflicting child row and survive a replacement that commits during the wait. For example, an old enqueue waiting behind reauthentication must observe the new credentials after the lock is released and cannot recreate the just-deleted model exclusion. Priority observation insertion and clearing use the same boundary.

A completed paid verification is not the end of the request window. If a first Free sample arrives while time and attempts remain, verification reopens after 15 seconds with a new generation and the original expiry/budget. For example, a paid result on attempt one followed by Free can use attempt two to confirm the downgrade; a delayed completion from the first generation cannot close the reopened work. Repeated model errors still do not reset the window, and exhausted work stays exhausted.

When cancellation or a timeout reaches a priority worker during OAuth refresh, that waiter drains the shared exchange and guarded persistence before propagating cancellation. The upstream may already have consumed the old refresh token, so cancelling the exchange can strand the account. Ordinary request waiters retain their existing detach behavior. Shutdown can consequently take longer than the priority fetch timeout while the existing bounded authentication exchange/persistence finishes; HTTP clients and database resources stay available until the scheduler returns. This does not enable token refresh merely because a plan changed.

## Free evidence arriving before completion

A paid sample and its final priority-check completion are separate writes. An independent first Free observation advances the existing generation even when the old check is still running, keeping its request time and attempt budget. The old completion then cannot hide the new pending verification. A priority worker's own first Free observation already has an owned delayed retry, so it does not enqueue itself again.

For example, a Plus sample is processed, a fleet refresh records Free, and the Plus check finally completes. The account summary continues to show pending verification, and a subsequent agreeing Free sample confirms the downgrade. Exhausted attempts and the original two-minute expiry still bound this work; no new schema or setting is needed. The account-row lock and credential guards remain in place for reauthentication contention.

First-Free enqueue also checks that shared evidence still contains exactly one Free observation for the same identity, after taking the account-row lock. This guards both new insertion and reopening. For example, if the fleet refresh pauses after recording its first sample, a priority worker may consume the second sample before the fleet enqueue resumes. That delayed enqueue leaves the confirming generation intact, so the worker can save Free without wasting its last attempt. A model-entitlement rejection can still enqueue work independently of Free evidence.

Agreeing Free evidence is consumed only after metadata persistence succeeds. Routine token rotation can invalidate the worker's exact-token guard between confirmation and persistence even though the account's identity and check generation remain valid. Keeping the observations lets the remaining attempt reload the rotated credentials and finish within the original budget. For example, with attempt one already consumed, a rotation conflict on attempt two retains two Free observations; attempt three writes Free, clears evidence and completes verification without reauthentication. Actual import/reauthentication still deletes the old evidence/check atomically, and successful priority clearing remains generation-fenced. A conflict on the final attempt still falls back to the existing fleet refresh policy; retaining evidence does not create extra attempts.

Ordinary refreshes have no check generation, so evidence clearing checks the persisted credential generation from the observed account. The database store takes the account-row lock before evaluating this condition, including for an ordinary clear waiting behind replacement on PostgreSQL. For example, reauthentication can replace credentials and install a new first Free observation after an older refresh saved Free; the old clear then leaves the new observation intact. Routine rotation preserves that generation, allowing paid samples to discard contradicted Free evidence and first-Free samples to enqueue verification. Import/reauthentication atomically increments the generation even with identical token values, invalidating stale mutations. The generation also participates in the evidence fingerprint; existing observations/checks with the old fingerprint format are conservatively restarted or completed on their next lookup.
