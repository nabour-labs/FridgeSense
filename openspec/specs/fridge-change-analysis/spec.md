# fridge-change-analysis Specification

## Purpose
Asks Amazon Bedrock Nova what was put into or taken out of the fridge during one door opening, turns its answer into validated changes, and records what each analysis cost.

## Requirements

### Requirement: One Nova request per door opening
For a door opening, the system SHALL send one Bedrock Converse request to the configured model (default `us.amazon.nova-2-lite-v1:0`) containing the stills in time order (each preceded by a text label `Image <n> of <total>`), then a final text with the instructions and the current inventory's item names in square brackets, with `temperature` 0 and the tool `record_fridge_changes` forced. When the account has reference images or custom instructions, the request SHALL also carry them as set out in the requirement "Owner's config sent with each analysis".

#### Scenario: Request built from stills and inventory
- **WHEN** a door opening has stills 1–4 and the inventory holds `milk` and `eggs`
- **THEN** the request's content is `Image 1 of 4`, still 1, `Image 2 of 4`, still 2, … still 4, then a text containing `[milk, eggs]`; `toolConfig.toolChoice` is `{"tool": {"name": "record_fridge_changes"}}`; `inferenceConfig.temperature` is 0

#### Scenario: Empty inventory
- **WHEN** the inventory is empty
- **THEN** the final text contains `[]`

#### Scenario: Stills sent as bytes
- **WHEN** the request is built
- **THEN** each image block is `{"format": "jpeg", "source": {"bytes": <the stored still>}}` and at most 4 images are sent

### Requirement: Answer validated before use
The system SHALL read the `toolUse.input` named `record_fridge_changes` from anywhere in the response content and accept it only if it has `added` and `removed` lists of objects with a non-empty `item`. Each change SHALL be normalized: unknown `category` becomes `"other"`, missing or non-positive `quantity` becomes 1, and `confidence` is clamped to 0–1.

#### Scenario: Valid answer
- **WHEN** Nova returns `stopReason = "tool_use"` with input `{"added": [{"item": "milk", "category": "dairy", "quantity": 1, "confidence": 0.92}], "removed": [{"item": "eggs", "category": "dairy", "quantity": 2, "confidence": 0.71}]}`
- **THEN** the analysis has one added change (milk, dairy, 1, 0.92) and one removed change (eggs, dairy, 2, 0.71)

#### Scenario: Text before the tool call
- **WHEN** the response content is a text block followed by the `toolUse` block
- **THEN** the tool input is still found and used

#### Scenario: Values out of range
- **WHEN** a change has `category = "snacks & treats"`, `quantity = 0` and `confidence = 1.4`
- **THEN** it becomes category `other`, quantity 1, confidence 1.0

#### Scenario: Invalid answer retried once
- **WHEN** the first response has no `record_fridge_changes` tool call (for example `stopReason = "end_turn"` or `"malformed_tool_use"`) or lacks `added`/`removed`, and the second response is valid
- **THEN** exactly two requests are made and the second answer is used

#### Scenario: Invalid answer twice
- **WHEN** both responses are invalid
- **THEN** the door event's `status` becomes `"analysis_failed"` and the inventory is unchanged

### Requirement: Bedrock errors handled
Throttling, timeouts and service errors (`ThrottlingException`, `ModelTimeoutException`, `ServiceUnavailableException`, `InternalServerException`) SHALL be retried up to 3 attempts with backoff. Any other Bedrock error, or exhausted retries, SHALL set the door event's status to `"analysis_failed"`.

#### Scenario: Throttled once
- **WHEN** the first call raises `ThrottlingException` and the second succeeds
- **THEN** the analysis completes normally

#### Scenario: Request rejected
- **WHEN** the call raises `ValidationException` or `AccessDeniedException`
- **THEN** it is not retried and the door event's `status` is `"analysis_failed"`

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

### Requirement: Owner's config sent with each analysis
When the account has reference images, the request SHALL begin with the text `Reference images: examples of items in this fridge. They are not part of this door opening.`, then, oldest first, `Reference <n>: <annotation>` followed by that image. The stills follow as before. Custom instructions SHALL be appended to the final text, after the inventory and before the tool instruction, as `Owner's instructions: <text>`.

#### Scenario: References before stills
- **WHEN** the account has references "milk bag" (added first) and "soda can", and the door opening has stills 1–4
- **THEN** the content starts with the reference header text, `Reference 1: milk bag`, its image, `Reference 2: soda can`, its image, and then `Image 1 of 4`, still 1, … still 4 and the final text

#### Scenario: Reference images as bytes
- **WHEN** references are sent
- **THEN** each reference image block is `{"format": "jpeg", "source": {"bytes": <the stored reference bytes>}}`, and the 4-still limit still applies to the stills alone

#### Scenario: Custom instructions in the final text
- **WHEN** the custom instructions are `Count yogurt cups individually.`
- **THEN** the final text contains `Owner's instructions: Count yogurt cups individually.` after the inventory list, and still ends by asking to call `record_fridge_changes`

#### Scenario: No config
- **WHEN** the account has no references and empty custom instructions
- **THEN** the request is identical to one built without config: no reference header and no `Owner's instructions` text

#### Scenario: Config changed between openings
- **WHEN** a reference is deleted after one door opening and before the next
- **THEN** the next opening's request no longer includes that reference

### Requirement: Bounded Bedrock call time
Each Bedrock request SHALL be sent once by the client (no client-side retries) with a read timeout of 30 s, so that the analysis step's two Nova attempts finish within the pipeline task's 90 s limit. A client-side read or connect timeout SHALL be treated like a retryable Bedrock error (`BedrockRetryable`), so the workflow's backoff retries apply to it.

#### Scenario: Client sends one attempt
- **WHEN** the pipeline builds its Bedrock client
- **THEN** the client's total attempts is 1 and its read timeout is 30 s

#### Scenario: Read timeout is retryable
- **WHEN** a Nova request times out on the client side (read or connect timeout)
- **THEN** the analysis raises `BedrockRetryable` and a `nova_error` warning is logged with `error_code` `ReadTimeout` or `ConnectTimeout`

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
