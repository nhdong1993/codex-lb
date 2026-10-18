## MODIFIED Requirements

### Requirement: Source response continuity preserves credential ownership

Recorded source response anchors MUST resolve within the presenting API key and public model scope and remain on the recorded source. A known owner that is disabled, removed, disallowed, saturated or cooling MUST NOT cause a switch to another source. Conflicting ownership or missing ownership in a multi-source pool MUST fail closed. Existing subscription-owned and file-pinned routing MUST remain authoritative. Ownership lookup failures MUST fail closed without dispatch. When a candidate source's only conflicting ownership is that same source's earlier credential, endpoint or upstream-model revision, the proxy MUST NOT forward the stale opaque state; it SHALL instead forward a portable projection of the stale input prefix to that same source as specified below, and otherwise MUST fail closed.

#### Scenario: Resume on a different replica

- **GIVEN** a completed source response is recorded in shared request logs
- **WHEN** the client continues with its response ID on another replica
- **THEN** the same eligible source handles the request regardless of rotation state

#### Scenario: Unknown or inaccessible owner

- **WHEN** an anchor has no unambiguous permitted owner in a pool or its recorded owner is no longer eligible
- **THEN** the response reports unavailable continuity without contacting a different source

#### Scenario: File and subscription ownership wins

- **WHEN** the payload references an uploaded file or a subscription-owned response
- **THEN** the existing account ownership path handles the request and source pooling does not bypass its restrictions

#### Scenario: Credential-bound history cannot rotate

- **WHEN** a request includes conversation state, encrypted reasoning, item references or other non-portable state
- **THEN** a multi-source pool MUST resolve unambiguous ownership or decline without dispatch
- **AND** the request MUST NOT fail over to another credential
- **AND** conflicting references and credential replacement MUST fail closed, except for the same-source stale-state projection

#### Scenario: Known source owner has no eligible candidate

- **WHEN** a known source-owned request has no matching eligible source because sources were removed or their capability no longer matches
- **THEN** it MUST fail closed before subscription dispatch
- **AND** lookup MUST retain the original public-model scope when request normalization changes its spelling
- **AND** authoritative file and subscription ownership handling MUST retain its existing precedence

#### Scenario: Saving an identical upstream token

- **WHEN** an operator saves exactly the currently configured upstream token without changing its endpoint or upstream model
- **THEN** existing response ownership MUST remain usable on the same source across backends
- **AND** replacing the token with a different credential MUST still invalidate incompatible continuity

#### Scenario: Overrides introduce different continuity references

- **WHEN** source request overrides change reference-bearing input, conversation or previous-response state
- **THEN** conflicting or unknown ownership in the effective forwarded payload MUST be rejected before upstream dispatch
- **AND** each effective reference MUST be individually resolved; a known response owner MUST NOT authorize another unresolved response ID
- **AND** ownership SHALL be evaluated separately for each candidate; references introduced only by another candidate MUST NOT block a valid owner
- **AND** a post-generation publication failure MUST NOT be the first ownership check for those references

#### Scenario: Unresolved tool outputs refer to another owner

- **WHEN** a request combines an anchor owned by one source with an unresolved tool result whose `call_id` belongs to another source
- **THEN** it MUST fail closed without dispatch
- **AND** only complete, ordered, type-matched call/result pairs without opaque upstream state SHALL bypass reference ownership; partial calls and mismatched results MUST retain their ownership checks
- **AND** a complete pair retaining its returned bookkeeping item IDs SHALL use the same portability classification without changing the forwarded body

#### Scenario: Same-source reconfiguration projects stale inline state

- **GIVEN** a source served earlier turns of a conversation and its token, endpoint or upstream-model mapping has since changed
- **WHEN** a request resends that conversation's input and every conflicting owner of its references is the same source under an earlier revision
- **THEN** the proxy MUST dispatch the request to that same source after projecting the input prefix that ends at the last input item whose own references (including the item IDs and call IDs of complete call/result pairs) were recorded under an earlier revision of that source
- **AND** the projection MUST drop `reasoning` items and completed `web_search_call`, `tool_search_call` and `tool_search_output` items, MUST remove the `id` of every other prefix item, and MUST keep `call_id` values and all remaining content
- **AND** input items after that prefix MUST be forwarded unchanged
- **AND** the forwarded body MUST NOT contain any item ID or encrypted content recorded under the earlier revision, including one reintroduced by an input override; `call_id` values of complete call/result pairs are not continuity references and remain
- **AND** the projected request MUST NOT fail over to another source, and the earlier-revision references MUST NOT be recorded under the current revision
- **AND** ownership MUST be re-checked on both the projected client request, so its anchors stay authoritative even when an override removes them, and the projected effective body, before dispatch

#### Scenario: Stale state that projection cannot remove still fails closed

- **GIVEN** a source's token, endpoint or upstream-model mapping has changed
- **WHEN** an earlier-revision reference is a `previous_response_id`, `conversation`, `prompt`, container or vector-store reference, a compaction item's encrypted content, or an unresolved tool `call_id`, or the stale prefix contains an `item_reference`, or the projection would leave no input items
- **THEN** the request MUST fail with the existing 409 envelope without upstream dispatch
- **AND** a reference owned by a different source MUST NOT be projected away to enable a switch
