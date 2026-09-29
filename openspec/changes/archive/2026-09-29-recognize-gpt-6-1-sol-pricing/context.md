## GPT-6.1 Sol cost recognition

The missing catalog entry left GPT-6.1 Sol unpriced across the shared request-cost path. Its [official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol), checked on 2026-09-29, lists Standard input/cached-input/output rates of `$2 / $0.10 / $10` per million tokens, Fast at twice Standard, and Flex at half Standard. Prompts above 272,000 total input tokens multiply input/cache rates by two and output by 1.5.

A separate entry preserves model identity and the lower cache-hit rate compared with GPT-6 Sol. Existing calculator fields cover these rates without new runtime settings. Cache writes, Batch, and regional premiums remain outside the current token-accounting contract.

For example, 200,000 input tokens including 100,000 cached tokens and 100,000 output tokens cost `$0.20 + $0.01 + $1.00 = $1.21` at Standard. Fast is `$2.42`; Flex is `$0.605`. Retaining the old Sol cached rate would incorrectly produce `$1.22` at Standard.

Deployment enables pricing for new requests and settlements. Historical persisted costs and settled quota counters are preserved; null-cost request details can use the existing calculated breakdown fallback, while historical aggregates still use stored costs. This change includes no production data rewrite or deployment. Unknown GPT-6.1 families remain unpriced.
