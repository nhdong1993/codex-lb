## Why

Stored ID-token subscription claims can retain a previous billing period after renewal. A live subscriptions request returned an October deadline for an account whose ID token still recorded September, causing misleading remaining time.

## What Changes

- Fetch subscription terms in the background through the account's configured route using the browser-compatible HTTP client proven by tool_vip_v2.
- Persist successful snapshots for all replicas; prefer them to ID-token metadata and identify the displayed source.
- Preserve the last successful result on transient failures without changing account health or refreshing credentials.
- Render all subscription durations as unpadded whole days/hours (`5d 8h`).

## Capabilities

### Modified Capabilities
- `account-subscription-term`: live snapshots, safe fallback, refresh ownership and compact formatting.

## Impact

Accounts ORM and additive migration, background scheduler/lifespan, subscription HTTP client, summary mapping, frontend schema/components/locales. Adds curl_cffi for this endpoint only; existing proxy request transports remain as configured.
