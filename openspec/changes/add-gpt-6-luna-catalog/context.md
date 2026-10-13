# GPT-6 Luna bootstrap catalog corrections

## Evidence and decisions

The saved Codex endpoint response at `/tmp/codex-endpoint-codex-models.json`
was inspected read-only. Its GPT-6 Luna entry advertises 26 plans. The initial
bootstrap entry missed `edu_plus`, `edu_pro`, `enterprise_cbp_automation`,
`enterprise_cbp_trial`, and `sci`; the existing account-eligibility gate does
not alias these labels to other plans, so that omission rejected supported
accounts at cold start. Preserve all existing plan labels and add these five.

Fast (`priority`, description `1.5x speed`) is available, but the saved default
service tier is null. Availability is not a default selection: preserve the
existing serializers rather than changing either endpoint's response shape.
For example, `/backend-api/codex/models` and
`/v1/models?client_version=0.155.0` emit `default_service_tier: null`, while
ordinary `/v1/models` omits `metadata.default_service_tier`. Both still advertise
Fast. Only the Codex-client representation promises maximum context, Responses
Lite, code-mode tools, and available plans.

## Constraints and verification scope

This is a static fallback correction, not an account-routing policy change.
A refreshed or persisted snapshot remains authoritative. Long upstream
instruction templates remain intentionally outside the bundled fallback.
Regression tests exercise the unchanged account-eligibility helper with
canonical and whitespace/case-varied plan spellings, plus real discovery
routes for both response shapes. The saved endpoint and local CLI catalog are
not modified. Author-verified requirements and stable context are synced to
`model-catalog-compat` before independent review of the combined diff. No change
is archived; independent review of the corrected catalog remains pending.

## Author verification (2026-10-11)

The new targeted regressions first failed on the original implementation:
5 failed (canonical and normalized account eligibility, ordinary discovery,
and both Codex-client discovery paths). After correction, the focused
bootstrap/service-tier/retained-metadata slice passed: **29 passed,
93 deselected in 21.52s**. This includes live-snapshot precedence for GPT-6 Luna.
The previous full catalog result of 118 passed was not rerun; broadening was
unnecessary for the two static metadata corrections.

Scoped Ruff format/lint and ty checks passed for the three permitted Python
files. OpenSpec 1.14.0 strict validation of this change passed. The supplied
67/67 nonstrict main-spec baseline and the older global strict result
(7 passed, 60 warning-induced failures) are baseline evidence, not exceptions
granted by this author. The independent reviewer decides actual gate
applicability. Exact correction commands and results are in
`/tmp/codex-model-plan-routing/verification/catalog-fix-*.log`.
The final documentation checks and shared limitations are recorded in
[the integration verification record](../configure-subscription-model-plan-routing/verification.md).
These are author checks, not independent review or approval. The earlier
`CHANGES_REQUIRED` review identified the three corrected P2 findings; that
review is not approval of the corrected implementation.

The separate CLI catalog sync was already complete: 30 endpoint IDs, no added
or removed IDs. This documentation integration neither repeats that sync nor
changes CLI configuration, authentication, catalog files, or production.
