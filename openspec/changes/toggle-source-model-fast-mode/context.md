# Context: toggle-source-model-fast-mode

## How Codex decides to offer Fast

Codex builds its Fast option from the model catalog. A model is Fast-capable when its catalog entry lists the priority tier in `service_tiers` (newer clients) or `fast` in `additional_speed_tiers` (older clients). When the user turns Fast on, Codex sends `service_tier: "priority"` for such a model. For any other model it sends no tier at all.

Request logs from 2026-10-12 show the effect. The same API key sent `priority` on 294 `gpt-6-luna` requests and on none of its 247 `ch-relay/gpt-6-astra` requests that day, because no source model advertised a tier.

The proxy copies unknown `raw_metadata_json` keys into the Codex catalog entry and maps the tier keys into `/v1/models` metadata, so declaring the keys is enough. No backend change is needed.

## Decisions

- **Advertise only.** The switch controls what clients are offered. It does not strip or reject `service_tier` on requests. Before this change, an SDK client could already send `service_tier` to a source; stripping it when the switch is off would change that behavior. The global `prohibitFastMode` still strips the priority tier everywhere.
- **Default off.** Source models advertised nothing before. Starting new rows off keeps zero-config behavior and avoids promising a speed-up the source may not deliver.
- **Write both keys.** `service_tiers` serves current Codex clients and `additional_speed_tiers` serves older ones. Bootstrap subscription entries carry both.
- **Preserve custom entries.** A model with any priority entry shows the switch on, and a save that does not change the switch leaves the tier metadata as stored, so a hand-written entry such as "2x speed, increased usage" survives. Turning Fast off removes only priority-equivalent entries, so `flex` or other tiers survive.
- **Neutral description.** The added entry says "Priority processing" rather than a speed multiplier, because the source's real behavior is unknown.

## Failure modes

- **Pinned client catalog.** Clients installed by the key-dashboard installer read `model_catalog_json` from a local file. They see the switch's effect only after re-running the installer, or after refreshing that file, and starting a new Codex session.
- **Source ignores the tier.** On 2026-10-17, two direct requests to the ch-relay source (backed by Plus accounts) both returned `service_tier: "auto"`, with and without `priority`. Codex then shows Fast but the source does not speed up. Turn the switch off for such sources.
- **Request logs.** Source-routed request logs record the requested tier. They do not record the tier the source reports, and they carry no latency, so speed checks need the source's own logs.

## Example

Metadata of `ch-relay/gpt-6-astra` after turning Fast on:

```json
{
  "upstream_model": "gpt-6-astra",
  "block_subagents": true,
  "service_tiers": [{"id": "priority", "name": "Fast", "description": "Priority processing"}],
  "additional_speed_tiers": ["fast"]
}
```

Its Codex catalog entry then lists Fast. After the client refreshes its catalog, selecting Fast sends `service_tier: "priority"`, which the proxy forwards to the source.
