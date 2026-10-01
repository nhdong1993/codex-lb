# API Keys Context

See [API key requirements](spec.md) for normative requirements.

## Daily reset schedule

The reset contract is defined in [Weekly token usage reset](spec.md#requirement-weekly-token-usage-reset).

Daily API-key limits follow the Ho Chi Minh City calendar using the operator-requested fixed UTC+7 offset. Persisted timestamps remain naive UTC; the host timezone does not affect calculation. Other limit windows retain their existing durations.

For example, a daily limit created at `2026-09-06 16:59 UTC` resets at `2026-09-06 17:00 UTC`, which is `2026-09-07 00:00` in Ho Chi Minh City. A daily limit created exactly at `17:00 UTC` receives the following day's `17:00 UTC` reset timestamp.

The existing leader-gated alignment pass runs at `16:50 UTC` (`23:50` local time), ten minutes before the reset boundary. It moves existing daily reset timestamps while preserving usage counters. Expired counters clear through request-time lazy expiry or the hourly background fallback; the alignment pass itself does not clear counters. Existing strict expiry comparisons process a limit once the clock is past its reset timestamp.

No database migration or host timezone change is needed. Fresh and explicitly reset limits use the local boundary immediately after deployment. Existing future timestamps converge at the next alignment pass, while expired timestamps converge when reset. Deploying after `16:50 UTC` can leave legacy timestamps until the next day's pass. Alignment logs identify `Asia/Ho_Chi_Minh` midnight and record the target as UTC.

## Request-aware reservation estimate

The admission budget for token and `cost_usd` limits (Requirement
"Request-aware API-key usage reservations") sizes the input side from the
forwarded request payload: `min(utf8_length(serialized_payload_minus_caps), 8192)`.
Two implementation notes keep that value exact while avoiding redundant work on
the hot path:

- **Shared dump.** `ResponsesRequest.to_payload()` is deterministic, so the
  HTTP bridge prepare path computes it once and threads the same dict through
  client-metadata derivation, the forwarded `response.create` frame and
  `estimate_api_key_request_usage(payload, upstream_payload=...)`. The budget,
  frame bytes and input fingerprints are byte-identical to computing each stage
  from its own dump. When the prepare path rewrites the request (replayed
  side-effect tool-call dedupe under `previous_response_id`) the caller's dump
  is discarded and recomputed from the rewritten request, so the forwarded
  frame never carries un-deduped input. Callers that do not hold a dump keep
  the default single-argument form.
- **Early-exit serialization.** Because the estimate is capped at 8192 bytes,
  the estimator returns the cap as soon as it is proven: an `instructions`
  string of 8192+ characters alone suffices (a JSON string literal is never
  shorter than its character count), otherwise the payload is streamed through
  the same `sort_keys`/`ensure_ascii=False` encoder and stopped once 8192 bytes
  have been produced. Sub-cap payloads still yield the exact serialized length.
  The opaque-context checks (`previous_response_id`, `conversation`, file or
  image references) run before either shortcut, so the conservative `None`
  budget is unchanged.

Edge: a lone surrogate (`"\ud800"`) anywhere in the payload used to raise
`UnicodeEncodeError` (HTTP 500) from the full dump. It now raises only when it
sits in a chunk that is actually UTF-8 encoded, i.e. within the first ~8 KiB of
serialized output and not inside a string literal that the length shortcuts
(`instructions` >= 8192 chars, or a single chunk that alone covers the
remaining budget) prove the cap without encoding. Surrogates skipped that way
yield the 8192 cap like any other large payload.

## Missing image choices

The Images endpoints already accept image model IDs, but the API-key picker used a catalog built for conversational models. The fix supplements the dashboard catalog from the same allowlist used by Images validation. See [the image-model picker requirements](spec.md#requirement-api-key-model-picker-includes-supported-image-models).

This list represents supported request model names, not a guarantee that every connected account can generate images. Existing authentication and model restrictions still apply. The public Responses/Codex catalogs retain their existing behavior. Adapter entries carry `imageOnly=true` so the Automations picker, which shares the dashboard catalog, can exclude them from Responses jobs.

For example, an operator can create a key with `allowedModels: ["gpt-image-2"]`, reopen its edit dialog and replace it with `gpt-image-1-mini`. An unrestricted key (`All models`) already permits these names subject to other policies; this fix makes explicit image-only restrictions configurable in the UI.

The backend addition requires no migration or new setting. After deployment, reload the dashboard to refresh the cached model list. Bootstrap and refreshed catalogs are both supplemented; duplicate IDs appear once.

## GPT-6 request cost recognition

GPT-6 Astra, Sol, and Luna share the native pricing path used by request logs,
API-key reservations, settlement, and aggregate estimates. The rates were
verified on 2026-09-23 against [OpenAI pricing](https://developers.openai.com/api/docs/pricing)
and the [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Sol](https://developers.openai.com/api/docs/models/gpt-6-sol), and
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) model pages.
See [GPT-6 request cost requirements](spec.md#requirement-gpt-6-request-cost-pricing-is-recognized).

Each family has its own price entry and suffixed aliases; there is no generic
GPT-6 fallback that could charge an unknown future family at the wrong rate.
Fast uses twice the applicable standard short- or long-context rates, with
total input including cache hits selecting the context band. The implementation
reuses the existing tier fields without runtime configuration or price fetching.
Cache-write billing, Batch processing, and regional surcharges remain outside
the existing token-accounting contract.

For example, a standard Sol request with 200,000 input tokens (100,000 cached)
and 100,000 output tokens costs `$0.20 + $0.02 + $1.00 = $1.22`. Fast costs
`$2.44`; Flex costs `$0.61`. At exactly 272,000 input tokens, short-context
rates still apply.

Deployment enables recognition for new requests and settlements. Persisted
historical costs and settled quota counters are retained. Existing null-cost
rows can gain calculated request-detail breakdowns, while historical aggregates
remain based on persisted costs. No database migration or production data
rewrite is included.

## GPT Image 2.5 key restrictions

The shared Images allowlist now contributes Sunburst and Flare to the existing
API-key picker, alongside the four earlier image IDs. Saving and reopening a
key preserves each exact ID. Adapter-only entries are excluded from Automations
and are not injected into public `/v1/models` simply because the dashboard can
select them. See the [picker requirement](spec.md#requirement-api-key-model-picker-includes-supported-image-models).

For example, `allowedModels: ["gpt-image-2.5-sunburst"]` without an enforced
model permits Sunburst and denies Flare. If a key enforces Flare and allows it,
requests use Flare's parameter profile and Flare-scoped limit even when the
client supplies Sunburst. A request cannot evade an exhausted Flare limit by
naming another variant. Image usage is settled once under the effective public
ID; aggregate pricing and upstream-availability limits are explained in the
[Images context](../images-api-compat/context.md#gpt-image-25-variants).

The addition needs no migration or new configuration. After deployment,
reloading the dashboard refreshes the shared model catalog. Rollout is separate
from local implementation and verification.

## GPT-6.1 Sol cost recognition

See the [GPT-6.1 Sol requirement](spec.md#requirement-gpt-61-sol-request-cost-pricing-is-recognized).

The missing catalog entry left GPT-6.1 Sol unpriced across the shared request-cost path. Its [official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol), checked on 2026-09-29, lists Standard input/cached-input/output rates of `$2 / $0.10 / $10` per million tokens, Fast at twice Standard, and Flex at half Standard. Prompts above 272,000 total input tokens multiply input/cache rates by two and output by 1.5.

A separate entry preserves model identity and the lower cache-hit rate compared with GPT-6 Sol. Existing calculator fields cover these rates without new runtime settings. Cache writes, Batch, and regional premiums remain outside the current token-accounting contract.

For example, 200,000 input tokens including 100,000 cached tokens and 100,000 output tokens cost `$0.20 + $0.01 + $1.00 = $1.21` at Standard. Fast is `$2.42`; Flex is `$0.605`. Retaining the old Sol cached rate would incorrectly produce `$1.22` at Standard.

Deployment enables pricing for new requests and settlements. Historical persisted costs and settled quota counters are preserved; null-cost request details can use the existing calculated breakdown fallback, while historical aggregates still use stored costs. This change includes no production data rewrite or deployment. Unknown GPT-6.1 families remain unpriced.
