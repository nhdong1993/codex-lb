# Review findings

This follows the archived `2026-10-07-fix-model-source-compaction` change. Review
reproduced both defects on `/v1/responses/compact` and
`/backend-api/codex/responses/compact`: four failing cases. Replacing only the
compact handler with its pre-change implementation made both subscription
compatibility cases pass. The implementation and tests are local; no deployment
is authorized by this correction.

Example: a subscription compact body with `model: gpt-5.1`, empty input and
`conversation: {"id": "conv_existing"}` must reach the existing compact service.
An ordinary Responses validator expects a string conversation and must not run
before that subscription routing decision.
