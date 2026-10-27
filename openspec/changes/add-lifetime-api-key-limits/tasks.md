## 1. Backend

- [x] 1.1 Add `LimitWindow.LIFETIME` and accept `lifetime` in limit rule validation
- [x] 1.2 Give lifetime limits a far-future `reset_at` that changes on every reset, and backfill from all history
- [x] 1.3 Report lifetime limit 429s without a reset time
- [x] 1.4 Alembic revision adding `lifetime` to the PostgreSQL `limit_window` enum

## 2. Dashboard

- [x] 2.1 Offer `Lifetime (no reset)` in the limit window select (en, ko, zh-CN)
- [x] 2.2 Add a confirmed `Reset usage` action to the API key edit dialog

## 3. Verification

- [x] 3.1 Unit and integration tests for lifetime windows, backfill, sweep, explicit reset and the 429 message
- [x] 3.2 Dashboard tests for the window option and reset confirmation
- [x] 3.3 Update `docs/api-keys.md`
