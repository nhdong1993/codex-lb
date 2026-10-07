## Decisions

Reuse `_source_ownership_miss_denial` whenever HTTP source selection returns no
source, regardless of why selection was suppressed. Its lookup includes current
and historical source ownership and legacy response logs, scoped to the same API
key and public/raw model. Known source state and subscription/file ownership
cannot both be satisfied; refuse instead of choosing either credential.

Keep the disabled-source probe conditional on neither file exclusion nor
subscription ownership. Merely configuring a source with the same model is not
source state and does not block a valid subscription request. Source-selected
requests keep the existing pool resolver. Apply the same boundary to ordinary
HTTP Responses continuations because compact output is replayed there as well
as in subsequent compact requests.

## Validation

Create genuine source compaction via a local HTTP upstream, retain the published
references, then add an actual subscription response log, registered turn-state,
or file pin. Assert HTTP 409 before source or subscription calls and before new
reservations. Exercise encrypted-only and item-only state, both compact routes,
HTTP triggers and ordinary Responses continuations. Preserve existing positive
subscription/file routing and source-only continuation tests. Run focused tests,
related routing suites, lint/type checks and strict OpenSpec validation.

Ordinary HTTP Responses does not use a turn-state header to suppress source
selection. Preserve that contract: when its retained state has a source owner,
an ordinary continuation keeps that source; the header never moves source state
to an account. Compact requests and terminal triggers retain their existing
turn-state subscription lookup and now reject conflicting source references.
