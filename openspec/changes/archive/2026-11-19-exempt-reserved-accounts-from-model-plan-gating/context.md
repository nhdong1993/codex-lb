# Context: exempt reserved accounts from model Plan gating

## Purpose

A key's reserved accounts are its dedicated capacity. The registry's model-to-Plan map is generic evidence ("this model is offered on these Plans"); it should not override an operator's explicit dedication. Direct evidence about the account itself (its own model catalog, tier-specific data, the access-controlled `ultrafast` tier) still wins, because that is what the upstream will enforce.

## Decisions

- **Only the Plan comparison is exempt.** Per-account catalog and tier data answer "can this account serve the request"; the Plan map answers "is this model usually offered on this Plan". Exempting the catalog would knowingly send requests the upstream rejects.
- **Other keys see the baseline load.** The selection-input cache is shared by all keys. Instead of mixing exempt accounts into the shared result (which changed other keys' error codes through quota and continuity branches), the owning key gets a second load with `plan_exempt_api_key_id`, cached under its own key id. Only keys that own a reserved account pay for the extra load.
- **Ownership is read from the same load.** The reload exempts only rows that still say `reserved_api_key_id == K`, so a reservation removed between the two loads does not leave a shared account exempt.
- **Bridge reuse uses the current request's key.** Bridge sessions keep an account snapshot from when they opened; the request's `ApiKeyData.reserved_account_ids` is current, so a removed reservation stops the exemption on the next turn.

## Constraints

- `load_balancer.py` and `http_bridge/mixin.py` sit at their line ratchets (`openspec/specs/proxy-architecture/spec.md`).

## Failure modes

- If the reserved account's Plan really cannot serve the model, the upstream rejects the request and the existing account/model-rejection retry excludes that account and selects once more in the usual order (another reserved account first), so a Plan-eligible pool account serves it only when it is the next pick.
- An already-open native WebSocket upstream keeps its account until it reconnects; reservation changes (exclusivity included) are not re-checked per frame on that transport, so a released reservation stops the exemption from the next connection.
- A sticky thread already bound to a shared account can still win over the reserved account (existing behavior).

## Example

Key K reserves `acc-plus` (Plan `plus`). The registry lists `gpt-x` only for `pro`. Shared `acc-pro` is on `pro`.

- K requests `gpt-x` → `acc-plus` is selected.
- `acc-plus` is cooling down → K gets `acc-pro`; a shared `plus` account is never selected.
- Key J requests `gpt-x` with no shared `pro` account → `no_plan_support_for_model`, as before.
