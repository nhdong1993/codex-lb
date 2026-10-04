## Context

On 2026-10-04, all three production catalog routes returned xhigh as the multi-agent effort for `gpt-6.1-sol`, alongside supported max and ultra levels. `_to_codex_model_entry` currently limits the Ultra max override to `gpt-6-astra`.

## Goals / Non-Goals

Apply the same Ultra max policy to subscription GPT-6.1 Sol. Preserve the existing Astra policy, other models, source-owned metadata, and explicit request effort semantics.

## Decisions

- Extend the existing exact model-name condition to include `gpt-6.1-sol`; retain the subscription-only and supported-effort guards. A broad family match would change unrelated models without a corresponding requirement.
- Continue overriding only outgoing catalog metadata. The registry remains faithful to upstream observations, and the proxy continues forwarding an explicit xhigh request as xhigh.
- Extend the existing API catalog tests across both policy models rather than duplicate the test suite.

## Risks / Trade-offs

Pinned catalogs and existing Codex sessions can retain the old xhigh value after deployment. Max can increase latency and token consumption; it is the requested Ultra behavior.

## Migration Plan

No schema or environment change is needed. After deployment, refresh pinned catalogs and start a new Codex session. For example, a refreshed `gpt-6.1-sol` entry with `multi_agent_reasoning_effort: "max"` makes Ultra select max. Reverting the model-name addition restores upstream policy on subsequent catalog refreshes.
