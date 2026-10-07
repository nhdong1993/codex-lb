# Mixed ownership review finding

The prior review sent real fixture output (`cmp_source` / `cipher-source`) back
to each standalone compact route with `previous_response_id` recorded for a
subscription account under the same API key. Both routes called the subscription
upstream with that source state. The return from continuity selection suppressed
the source ownership guard entirely.

Example: a source-owned encrypted compact item plus a subscription response ID
has no single valid upstream credential. A subscription anchor decides routing
only when retained references do not contradict it. Lookup errors must continue
to fail closed, without reserving quota. Tests and the correction are local.
