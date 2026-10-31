# API Key Authentication

API key auth is **disabled by default**. In that mode, only local requests to the protected proxy routes can
proceed without a key; non-local requests are rejected until proxy authentication is configured. Enable it in
**Settings → API Key Auth** on the dashboard when clients connect remotely or through Docker, VM, or container
networking that appears non-local to the service.

When enabled, clients must pass a valid API key as a Bearer token:

```
Authorization: Bearer sk-clb-...
```

## Protected routes

The protected proxy routes covered by this setting are:

- `/v1/*` (except `/v1/usage`, which always requires a valid key)
- `/backend-api/codex/*`
- `/backend-api/transcribe`

## Creating keys

Dashboard → API Keys → Create. The full key is shown **only once** at creation. Keys support optional expiration, model restrictions, and rate limits (tokens / cost per 5 hours / day / week / 7 days / month, or **lifetime**: a total budget that never resets on its own). In the key's edit dialog, **Reset usage** sets every limit's current usage back to 0 after a confirmation; periodic limits also start a new window.

Keys can also be scoped to specific accounts, so a key draws quota only from the accounts assigned to it:

![API keys with assigned accounts](screenshots/apis-assigned-accounts.jpg)

## Reserved accounts

**Reserved accounts (preferred)** dedicate accounts to one key: that key uses them first and falls back to its normal pool only while they are unusable, and no other key (nor a keyless request) can use them, including for `/v1/reset-credit`, `/v1/warmup` and a keyed quota-planner warm-now. An account belongs to at most one key: reserving an account another key holds returns `409 account_reserved_by_other_key`. For a key scoped to assigned accounts, its reserved accounts are added to the assignment. Deleting the key (or the account) releases the reservation. See [Routing](routing.md#reserved-accounts) for how selection treats them.

## Reasoning effort policies

A key can either enforce one reasoning effort or allow a selected non-empty set of client-requested efforts.
Leave the allowed-efforts selection empty to keep the existing unrestricted behavior. A request that explicitly
sets an effort outside its key's allowlist receives a `403 reasoning_effort_not_allowed` response. Requests that
omit a reasoning effort continue to use the model or upstream default.

The policy evaluates the effort selected by the client, including supported model aliases such as `-xhigh`.
Each configured effort is distinct: allowing `high` does not allow `xhigh`, and allowing `max` does not allow
`ultra`. The proxy still rewrites an allowed `ultra` request to the upstream wire value `max`.

![API key reasoning-effort policy](screenshots/apis-reasoning-efforts.jpg)

For wiring keys into each client, see [Client Setup](client-setup.md).

---

*Spec: [api-keys](https://github.com/Soju06/codex-lb/tree/main/openspec/specs/api-keys)*
