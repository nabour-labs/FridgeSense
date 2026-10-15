# Spec Delta

## MODIFIED Requirements

### Requirement: Cost logged per question
For each question the assistant starts, it SHALL log one `ask_agent` event with `outcome` (`answered` or the failure name), `rounds`, `tools`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` and `usd` summed over all model calls, and `ms`. Token counts and `usd` follow the same rules and Nova price settings as door-opening analysis, cache prices included. The question text SHALL NOT be logged.

#### Scenario: Answered question
- **WHEN** a question takes two model calls with usage 1200/40 and 1500/30 tokens at $0.00033/$0.00275 per 1K
- **THEN** one `ask_agent` event is logged with `outcome` `"answered"`, `rounds` 2, `input_tokens` 2700, `output_tokens` 70, `usd` 0.001084 and no question text

#### Scenario: Failed question still logs cost
- **WHEN** the first model call uses 1200/40 tokens and the second raises an error
- **THEN** one `ask_agent` event is logged with `outcome` `"bedrock_error"`, `input_tokens` 1200 and `output_tokens` 40

#### Scenario: Second round read from cache
- **WHEN** the first model call reports `inputTokens = 1200`, `outputTokens = 40` and no cache fields, and the second reports `inputTokens = 300`, `cacheReadInputTokens = 1200`, `cacheWriteInputTokens = 0` and `outputTokens = 30`, with default prices
- **THEN** the `ask_agent` event has `input_tokens` 1500, `cache_read_tokens` 1200, `cache_write_tokens` 0, `output_tokens` 70 and `usd` 0.000787

#### Scenario: No cache fields
- **WHEN** no model call reports cache fields
- **THEN** the `ask_agent` event has `cache_read_tokens` 0 and `cache_write_tokens` 0

## ADDED Requirements

### Requirement: Cache points in assistant requests
Every assistant model request SHALL end its `system` list with `{"cachePoint": {"type": "default"}}` after the system prompt text. No message SHALL carry a cache point, because Nova 2 Lite rejects one after a `toolResult` block (see measurement.md). Cache points SHALL never carry `ttl` and SHALL never appear in `toolConfig`.

#### Scenario: First round
- **WHEN** the assistant sends its first model request for "Do I have milk?"
- **THEN** `system` is `[{"text": <system prompt>}, {"cachePoint": {"type": "default"}}]`, the only message is the user question with no `cachePoint` block, and `toolConfig.tools` holds only `toolSpec` entries

#### Scenario: Tool results carry no cache point
- **WHEN** the model asks for `find_item` and the assistant sends its second request
- **THEN** the last message is a user message holding only the `toolResult` block, no message has a `cachePoint` block, and `system` is the same as in the first request

#### Scenario: One cache point per request
- **WHEN** the model asks for a tool in rounds 1, 2 and 3 and the assistant sends its fourth request
- **THEN** the request has exactly 1 cache point, at the end of `system`

#### Scenario: Cache points carry no ttl
- **WHEN** any assistant model request is sent
- **THEN** every `cachePoint` is exactly `{"type": "default"}`
