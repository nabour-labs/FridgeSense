# llm-usage-tracking Specification

## Purpose
Records the tokens, cached tokens and cost of every LLM call the system makes, per call in the logs and as running daily totals per account, so out-of-pocket model spend stays visible and checkable.

## Requirements

### Requirement: Usage logged for every LLM call
Every Bedrock model call that returns a response (door-opening analysis, including an invalid-answer retry, and each assistant round, including rounds of a question that later fails) SHALL log one `llm_usage` event with `source` (`analysis` or `assistant`), `account_id`, `model_id`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_input_tokens` and `usd`. It SHALL NOT log prompt text, the question, tool results or image bytes.

#### Scenario: Analysis call
- **WHEN** a door-opening analysis for account `acc-1` gets a response with `inputTokens = 1180`, `cacheReadInputTokens = 2000`, `cacheWriteInputTokens = 0` and `outputTokens = 96` from `us.amazon.nova-2-lite-v1:0`
- **THEN** one `llm_usage` event is logged with `source = "analysis"`, `account_id = "acc-1"`, `model_id = "us.amazon.nova-2-lite-v1:0"`, `input_tokens = 1180`, `cache_read_tokens = 2000`, `cache_write_tokens = 0`, `total_input_tokens = 3180`, `output_tokens = 96` and `usd = 0.000818`

#### Scenario: Retried analysis
- **WHEN** the first analysis response is invalid and the second is valid
- **THEN** two `llm_usage` events with `source = "analysis"` are logged, one per response

#### Scenario: Assistant rounds
- **WHEN** an assistant question takes two model calls
- **THEN** two `llm_usage` events with `source = "assistant"` are logged, one per call, in addition to the one `ask_agent` event

#### Scenario: Call that raises an error
- **WHEN** a Converse call raises `ThrottlingException` and returns no response
- **THEN** no `llm_usage` event is logged for that call

#### Scenario: No content in the log
- **WHEN** the assistant answers "Do I have milk?"
- **THEN** no `llm_usage` event contains the text `milk`, the system prompt, or any tool result

### Requirement: Cost computed from token counts
`usd` for one call SHALL be `(input_tokens × input price + output_tokens × output price + cache_read_tokens × cache-read price + cache_write_tokens × cache-write price) / 1000`, computed with exact decimals and rounded half-up to 6 decimals. Prices come from `NOVA_PRICE_IN`, `NOVA_PRICE_OUT`, `NOVA_PRICE_CACHE_READ` and `NOVA_PRICE_CACHE_WRITE` (defaults 0.00033, 0.00275, 0.0000825, 0). A usage field missing from the response SHALL count as 0.

#### Scenario: Uncached call
- **WHEN** a call reports `inputTokens = 1180` and `outputTokens = 96` only, with default prices
- **THEN** `cache_read_tokens = 0`, `cache_write_tokens = 0`, `total_input_tokens = 1180` and `usd = 0.000653`

#### Scenario: Cache write
- **WHEN** a call reports `inputTokens = 200`, `cacheWriteInputTokens = 1500` and `outputTokens = 96`, with default prices
- **THEN** `total_input_tokens = 1700` and `usd = 0.00033`

#### Scenario: Usage missing entirely
- **WHEN** a response has no `usage` object
- **THEN** every token count is 0 and `usd = 0.0`

### Requirement: Daily usage totals per account
After each logged call, the system SHALL atomically add the call's counts to the item `pk = ACCOUNT#<account_id>`, `sk = USAGE#<YYYY-MM-DD>` (date in the household time zone `TIME_ZONE`, default `America/Toronto`): `calls` +1, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `usd`, and per source `<source>_calls` +1 and `<source>_usd`. The item SHALL be created on the first call of the day.

#### Scenario: First call of the day
- **WHEN** account `acc-1` has no usage item for 2026-10-20 and an analysis call at 2026-10-20T14:00Z costs 0.000818 with 1180/2000/0/96 tokens
- **THEN** item `ACCOUNT#acc-1` / `USAGE#2026-10-20` has `calls = 1`, `input_tokens = 1180`, `cache_read_tokens = 2000`, `cache_write_tokens = 0`, `output_tokens = 96`, `usd = 0.000818`, `analysis_calls = 1` and `analysis_usd = 0.000818`

#### Scenario: Calls from both sources add up
- **WHEN** after that call an assistant call on the same household day costs 0.000506 with 1200/0/0/40 tokens
- **THEN** the item has `calls = 2`, `input_tokens = 2380`, `output_tokens = 136`, `usd = 0.001324`, `analysis_calls = 1`, `assistant_calls = 1` and `assistant_usd = 0.000506`

#### Scenario: Household day boundary
- **WHEN** `TIME_ZONE` is `America/Toronto` and a call happens at 2026-10-21T03:30Z (23:30 on Oct 20 in Toronto)
- **THEN** its counts are added to `USAGE#2026-10-20`

#### Scenario: Totals keyed by account
- **WHEN** accounts `acc-1` and `acc-2` each make one call on the same day
- **THEN** each call is added only to its own account's `USAGE#<date>` item

### Requirement: Totals failures never break the call
If adding to the daily totals fails, the system SHALL log an `llm_usage_store_failed` warning with `source`, `account_id` and the error name, and SHALL go on as if it had succeeded: the analysis result, the door event's `nova_usd` and the assistant's answer are unaffected.

#### Scenario: DynamoDB error during analysis
- **WHEN** the totals update raises `ProvisionedThroughputExceededException` during a valid analysis
- **THEN** an `llm_usage_store_failed` warning is logged, the `llm_usage` event is still logged, and the inventory changes and `nova_usd` are saved as usual

#### Scenario: DynamoDB error during a question
- **WHEN** the totals update raises an error during an assistant question that gets an answer
- **THEN** the assistant still returns the answer and logs `ask_agent` with `outcome = "answered"`

#### Scenario: Over-budget question records nothing
- **WHEN** the assistant reports `over_budget` without calling the model
- **THEN** no `llm_usage` event is logged and no usage item is changed
