# Spec Delta

## MODIFIED Requirements

### Requirement: Cost logged per analysis
For every Nova response the system SHALL log a `nova_cost` line with the model ID, door event, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` and `usd`, and SHALL add the analysis's total `usd` to the door event as `nova_usd`. `input_tokens` is `usage.inputTokens` (uncached input only); the cache counts are `usage.cacheReadInputTokens` and `usage.cacheWriteInputTokens`, or 0 when absent. `usd` prices each count at its configured per-1K-token price (defaults: $0.00033 input, $0.00275 output, $0.0000825 cache read, $0 cache write).

#### Scenario: Cost of one analysis
- **WHEN** a response reports `usage.inputTokens = 1180` and `usage.outputTokens = 96`
- **THEN** the `nova_cost` line has `usd = 0.000653` (rounded to 6 decimals) and the door event's `nova_usd` is 0.000653

#### Scenario: Cost of a retried analysis
- **WHEN** an invalid first response used 1000 input and 50 output tokens and the valid second one used 1180 and 96
- **THEN** two `nova_cost` lines are logged and `nova_usd` is the sum of both

#### Scenario: No cache fields in usage
- **WHEN** a response's usage has only `inputTokens = 1180` and `outputTokens = 96`
- **THEN** the `nova_cost` line has `cache_read_tokens = 0`, `cache_write_tokens = 0` and `usd = 0.000653`

#### Scenario: Cache read priced at the cache-read rate
- **WHEN** a response reports `inputTokens = 1180`, `cacheReadInputTokens = 2000`, `cacheWriteInputTokens = 0` and `outputTokens = 96`, with default prices
- **THEN** the `nova_cost` line has `input_tokens = 1180`, `cache_read_tokens = 2000`, `cache_write_tokens = 0` and `usd = 0.000818`

#### Scenario: Cache write priced at the cache-write rate
- **WHEN** a response reports `inputTokens = 200`, `cacheReadInputTokens = 0`, `cacheWriteInputTokens = 1500` and `outputTokens = 96`, with default prices
- **THEN** the `nova_cost` line has `cache_write_tokens = 1500` and `usd = 0.00033`

#### Scenario: Cache prices from configuration
- **WHEN** `NOVA_PRICE_CACHE_READ` is `0.0001` and `NOVA_PRICE_CACHE_WRITE` is `0.0005`, and a response reports `inputTokens = 0`, `cacheReadInputTokens = 1000`, `cacheWriteInputTokens = 1000` and `outputTokens = 0`
- **THEN** the `nova_cost` line has `usd = 0.0006`

## ADDED Requirements

### Requirement: Opt-in cache points in the analysis request
When `NOVA_CACHE_ANALYSIS` is `true`, the analysis request SHALL put a `{"cachePoint": {"type": "default"}}` block right after the last reference image (only when there are references) and another right after the last still, keeping all other content, order and wording unchanged. Cache points SHALL never carry `ttl` and SHALL never appear in `toolConfig`. When the setting is absent or any other value, the request SHALL contain no cache points.

#### Scenario: Caching off by default
- **WHEN** `NOVA_CACHE_ANALYSIS` is not set and the account has 2 references and the door opening has 4 stills
- **THEN** no content block in the request has a `cachePoint` key and the request equals the one built today

#### Scenario: Caching on with references
- **WHEN** `NOVA_CACHE_ANALYSIS` is `true`, the account has references "milk bag" and "soda can", and the door opening has stills 1–4
- **THEN** the content is the reference header, `Reference 1: milk bag`, its image, `Reference 2: soda can`, its image, `{"cachePoint": {"type": "default"}}`, `Image 1 of 4`, still 1, … still 4, `{"cachePoint": {"type": "default"}}`, then the final text with the inventory, owner's instructions and tool line

#### Scenario: Caching on without references
- **WHEN** `NOVA_CACHE_ANALYSIS` is `true`, the account has no references, and the door opening has 2 stills
- **THEN** the content has exactly one `cachePoint` block, placed between still 2 and the final text

#### Scenario: Cache point shape and placement limits
- **WHEN** `NOVA_CACHE_ANALYSIS` is `true` and a request is built
- **THEN** every `cachePoint` is exactly `{"type": "default"}` (no `ttl`), `toolConfig.tools` is `[<record_fridge_changes spec>]` with no `cachePoint` entry, and the request has at most 2 cache points

#### Scenario: Retry sends the same cached request
- **WHEN** `NOVA_CACHE_ANALYSIS` is `true` and the first response is invalid
- **THEN** the second request is identical to the first, cache points included

#### Scenario: Unrecognized setting value
- **WHEN** `NOVA_CACHE_ANALYSIS` is `yes please`
- **THEN** the request contains no cache points
