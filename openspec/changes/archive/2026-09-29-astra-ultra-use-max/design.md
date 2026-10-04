## Context

Codex 0.159.1 was observed sending `reasoning.effort: "xhigh"` after selecting Astra Ultra, using the upstream `multi_agent_reasoning_effort` catalog field. All three client catalog surfaces share `_to_codex_model_entry`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:** Select max for Astra Ultra through client-visible metadata, consistently across model discovery and installer exports.

**Non-Goals:** Change explicit xhigh requests, other model policies, model-source metadata, production runtime state, or client files on other machines.

## Decisions

- Override the outgoing extra field in the shared catalog serializer. Preserve registry raw metadata to keep discovery and persistence faithful to upstream. Mutating the registry would mix operator policy with upstream observations.
- Limit the policy to subscription `gpt-6-astra` advertising both max and ultra. This avoids inventing unsupported efforts or overriding custom providers.
- Use the existing catalog and request contract without a new setting. The operator explicitly requested this fixed Astra policy; a general configuration surface is unnecessary.

## Risks / Trade-offs

- A client pinned to a local JSON catalog retains xhigh until it refreshes its catalog and session. Document this activation step.
- Max may take more time or tokens; this is the requested behavior.
- This is an intentional exception to catalog passthrough. Regression tests cover unrelated models, source entries, and unsupported effort sets.

## Migration Plan

No migration is required. After a separately authorized deployment, refresh pinned client catalogs and start a new session. Reverting the serializer policy restores upstream metadata on subsequent catalog fetches.
