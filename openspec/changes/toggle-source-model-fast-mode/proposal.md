## Why

Codex shows its Fast option, and sends `service_tier: "priority"`, only for models whose catalog entry advertises the priority tier. Subscription models get that metadata from the upstream catalog. Source models get none, so Codex users never see Fast on models such as `http/gpt-6-astra`, even when the source behind them accepts the tier.

The proxy already forwards source metadata keys `service_tiers` and `additional_speed_tiers` to client catalogs. The dashboard has no way to set them: the source model editor exposes no raw metadata field. On 2026-10-17 an operator had to write the keys into the database by hand to test Fast on `ch-relay/gpt-6-astra`.

## What Changes

- Add a per-row **Fast** switch to the source model editor, next to the Sub-agents switch.
- Turning it on stores a priority `service_tiers` entry and a `fast` speed tier in that model's metadata. Turning it off removes only those entries. Other metadata keys and tier entries are kept.
- New rows start with Fast off, so existing and newly created sources advertise nothing until an operator opts in.
- The rows table scrolls sideways on narrow screens. Before this change the Model ID and Upstream model inputs shrank to a few characters at 390px; the extra column would have made them unusable.
- Add tests proving that a source model's declared tiers reach the Codex-native catalog, the key-dashboard installer catalog and `/v1/models`, and that a direct Responses request keeps its `service_tier` on the way to the source.

## Capabilities

### Modified Capabilities

- `model-source-routing`: add the per-model Fast switch requirement and the source tier advertisement requirement.

## Impact

- Frontend: model rows editor, form metadata helpers, edit/create dialogs, en/ko/zh-CN strings and tests.
- Backend: no code change; new integration tests pin the existing catalog passthrough and forwarding behavior.
- No migration, no new `CODEX_LB_*` setting, no API contract change and no new dashboard navigation item. The switch writes keys in `raw_metadata_json`.

## Non-goals

- Enforcing the switch in the proxy. A request that already carries `service_tier` is forwarded as before; only the global `prohibitFastMode` strips the priority tier.
- Guaranteeing that the source honors the priority tier. The switch only controls what the catalog advertises.
- Other service tiers such as `flex` or `ultrafast`.
- Subscription-account models, whose tiers come from the upstream catalog.
