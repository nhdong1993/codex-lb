# Model catalog compatibility context

The [specification](spec.md) defines the catalog contracts used by Codex and
OpenAI-compatible clients.

## Custom source collaboration capabilities

Codex assembles collaboration tools from model metadata. Importing only a
custom model's slug, context window, and reasoning levels can leave the client
without subagent tools even when the source supports them. Preserve the
upstream `tool_mode`, `multi_agent_version`, `multi_agent_reasoning_effort`,
`experimental_supported_tools`, and model instruction fields in source
metadata. `base_instructions` is projected into a first-class registry field;
other capability metadata is passed through as Codex catalog extras.

For example, a source model `custom/coder` declaring `tool_mode=code_mode_only`
and `multi_agent_version=v2` exposes those fields to Codex. The source tool
filter also derives `namespace` support from that version. Older running
replicas can use an explicit `namespace` entry in
`experimental_supported_tools` until the updated code is deployed.

A client with `model_catalog_json` pinned to a local file must refresh that
file and start a new Codex session to receive metadata changes. Keep the
source's verified HTTP transport settings: multi-agent capability does not
imply WebSocket or Responses Lite support. Do not replace a model's reserved
collaboration schema with a hand-written tool schema; upstream validates it.

## Custom source model aliases

A source can expose `cd/gpt-6-astra` while sending `cd/linxaq` upstream. The
public slug comes from the model row; `upstream_model` in raw metadata is
private routing configuration and is omitted from both model catalogs.
Instructions and multi-agent capabilities remain attached to the public alias.

Configure `cd/gpt-6-astra=cd/linxaq` in the source Models field. After rollout
and configuration, refresh any pinned client catalog before selecting the alias.
See [source alias operations](../model-source-routing/context.md#model-aliases)
for metadata preservation, token scope and rollback considerations.

## Subscription Ultra effort policy

For the subscription `gpt-6-astra` and `gpt-6.1-sol` models, the operator requested
max reasoning when selecting Ultra. Codex 0.159.1 uses
`multi_agent_reasoning_effort` from the catalog for this selection; the observed
upstream value was `xhigh`.
The [subscription Ultra requirement](spec.md#requirement-selected-subscription-models-advertise-max-for-ultra)
defines the deliberate exception to upstream catalog passthrough.

The policy is applied only to outgoing subscription Codex catalog entries for
these two exact model names supporting both `max` and `ultra`. Stored upstream
metadata remains intact. Other models and custom model sources keep their
declared policy, and an explicit xhigh request
still forwards as xhigh. Applying the override at catalog serialization avoids
turning ordinary xhigh requests into max requests.

For example, an upstream GPT-6.1 Sol entry with
`multi_agent_reasoning_effort: "xhigh"` is served as
`multi_agent_reasoning_effort: "max"`. With that catalog, selecting GPT-6.1 Sol Ultra
in Codex 0.159.1 produces `reasoning: {"effort": "max", "context": "all_turns"}`.
This changes the actual request effort and may increase latency or token use.

After deployment, refresh any local file configured by `model_catalog_json`
(for example, re-run the exported installer) and start a new Codex session.
A stale file or active session can continue to send xhigh even after the server
catalog changes. The native, versioned compatibility, and installer catalogs
share the same policy; none requires an environment setting or migration.

## GPT-6 Luna bootstrap metadata

The native `gpt-6-luna` fallback mirrors the saved Codex endpoint's 26 plan
labels, including `edu_plus`, `edu_pro`, `enterprise_cbp_automation`,
`enterprise_cbp_trial`, and `sci`. Omitting those labels incorrectly excludes
supported cold-start accounts: the eligibility helper does not alias them to
other plans. Case and surrounding whitespace normalize for catalog plan
eligibility. This broad entitlement vocabulary is separate from the narrower
operator [model Plan restriction vocabulary](../account-routing/context.md#subscription-model-plan-restrictions).
Catalog availability does not override that additional restriction or grant
access that an account lacks.

Fast (`priority`, `1.5x speed`) is available but is not the default: the bundled
Python value is `None`, matching the endpoint's null default. For example,
`/backend-api/codex/models` and `/v1/models?client_version=0.155.0` expose
`default_service_tier: null`, while ordinary `/v1/models` omits
`metadata.default_service_tier`. Both representations retain Fast. Only the
Codex-client representation promises maximum context, Responses Lite,
code-mode tools, and available plans; ordinary OpenAI metadata retains its
existing supported fields rather than acquiring Codex-only fields.

This is a conservative startup/offline fallback, not a complete clone of long
upstream instruction templates. Fresh persisted or refreshed snapshots retain
authority under the existing registry contracts, including replacement and
removal; future endpoint drift may require a new fallback correction. Source
models remain separate even when names collide. Static catalog metadata does
not configure the example three-model Free routing policy or alter live CLI
catalog files.
