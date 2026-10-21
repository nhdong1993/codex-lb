# Downgrade the service tier for Plan-restricted models

## Why

An operator can restrict a native model to some Plans, for example `{"gpt-6-luna": ["free"]}`. Clients with Fast mode on then send `service_tier: "priority"`. Account catalogs advertise that tier only on Plus accounts. Selection therefore narrows the pool to Plus first, and then the Plan restriction removes Plus. Every Fast request fails with `no_accounts` ("No available accounts. Service is operating in degraded mode"), although Free accounts could serve the request at the default tier.

## What Changes

- For a model in `modelPlanRoutingPolicies`, the proxy removes a requested or API-key-enforced non-default service tier when, according to an authoritative account catalog, none of the allowed Plans offers that tier for that model. The request is then routed and forwarded at the default tier.
- The tier is kept when an allowed Plan offers it (even if those accounts are currently unavailable), when the model is unconfigured, when catalog evidence is missing or not authoritative, when the model is unknown to the catalog, and when the policy cannot be read.
- Model-source dispatch and owner-forwarded requests are unchanged.
- Request logs record the effective tier; a diagnostic log line records the removed tier.

## Impact

- Request preparation on the subscription Responses (HTTP stream and non-stream), Chat Completions, compact and Responses websocket paths.
- Specs: `account-routing` (added requirement), `chat-completions-compat` and `responses-api-compat` (tier-preservation exceptions).
- No schema, migration, setting or UI change. Unconfigured models keep the explicit-tier behavior from #1248/#1409.
