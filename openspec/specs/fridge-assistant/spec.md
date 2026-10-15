# fridge-assistant Specification

## Purpose
Answers a free-text fridge question the way a voice assistant would: a Nova model connects to the FridgeSense MCP server as an MCP client, chooses which of its tools to call, and replies with a short sentence meant to be spoken. It stands in for Alexa+'s model in the demo.

## Requirements

### Requirement: Tools come from the MCP server
For each question, the assistant SHALL connect to the FridgeSense MCP server over Streamable HTTP at `https://<api host>/mcp/<mcp_key>`, list its tools, and offer exactly those tools to the model, each with the name, description and input schema the server gave.

#### Scenario: Four tools offered
- **WHEN** the assistant answers "Do I have milk?" against the FridgeSense MCP server
- **THEN** the original four tools `find_item`, `get_inventory`, `fridge_activity` and `last_opened` are still among the tools offered

#### Scenario: Six tools offered
- **WHEN** the assistant answers "Do I have milk?" against the FridgeSense MCP server
- **THEN** the first model request's tool config lists `find_item`, `get_inventory`, `fridge_activity`, `last_opened`, `oldest_items` and `low_stock`, each with its MCP description and its input schema as `inputSchema.json`

#### Scenario: MCP URL
- **WHEN** the API host is `abc123.execute-api.us-east-1.amazonaws.com` and `mcp_key` is `k1`
- **THEN** the assistant connects to `https://abc123.execute-api.us-east-1.amazonaws.com/mcp/k1`

### Requirement: Tool-use loop
When the model asks for one or more tools, the assistant SHALL call each one through MCP with the model's input, send every result back to the model in a single turn as a `toolResult` (JSON content, matched by `toolUseId`), and ask the model again. When the model ends its turn with text, that text SHALL be the answer. The result SHALL list the tools called, in order.

#### Scenario: Do I have milk
- **WHEN** the model first asks for `find_item` with `{"name": "milk"}`, the tool returns `{"query": "milk", "in_fridge": true, "total_count": 1, …}`, and the model then replies "Yes, you have 1 milk, added 2 minutes ago."
- **THEN** `find_item` is called once through MCP with `{"name": "milk"}`, the second model request carries that result as a `toolResult` with the same `toolUseId`, the answer is "Yes, you have 1 milk, added 2 minutes ago." and the tools are `["find_item"]`

#### Scenario: Open question combines tools
- **WHEN** the question is "What can I cook tonight?", the model asks for `get_inventory` with `{}`, then for `find_item` with `{"name": "eggs"}`, then replies with text
- **THEN** both tools are called in that order, the tools are `["get_inventory", "find_item"]`, and the answer is the model's final text

#### Scenario: Two tools in one turn
- **WHEN** the model asks for `find_item` (`{"name": "milk"}`) and `find_item` (`{"name": "eggs"}`) in the same turn
- **THEN** both are called and the next model request has one user message with two `toolResult` blocks, one per `toolUseId`

#### Scenario: No tool needed
- **WHEN** the model answers "Hello! Ask me what's in your fridge." without asking for a tool
- **THEN** the answer is that text and the tools are `[]`

### Requirement: Tool errors go back to the model
When an MCP tool call returns an error result, the assistant SHALL send it to the model as a `toolResult` with `status` `"error"` and the error text, and continue the loop.

#### Scenario: No camera linked
- **WHEN** `last_opened` returns an MCP error "No camera is linked yet. Link the Ring camera from the Ring app first." and the model then replies with text
- **THEN** the model receives a `toolResult` with `status` `"error"` and that text, and the answer is the model's reply

### Requirement: Answers read well aloud
The model SHALL be told to answer in at most two short sentences of plain spoken English, with counts and how long ago, without markdown or lists, and to use only what the tools return for facts about the fridge. Before returning, the assistant SHALL remove `<thinking>…</thinking>` blocks and the markdown characters `*`, `_`, `#` and `` ` ``, drop leading list markers, and collapse whitespace.

#### Scenario: Thinking and markdown removed
- **WHEN** the model's final text is "<thinking>The user wants milk.</thinking>**Yes**, you have\n- 1 milk."
- **THEN** the answer is "Yes, you have 1 milk."

#### Scenario: System prompt
- **WHEN** any question is asked
- **THEN** the first model request has a system prompt that asks for at most two short spoken sentences, no markdown, and fridge facts only from tools

### Requirement: Assistant failures are reported, not answered
The assistant SHALL report a failure, and give no answer, when the model or MCP call raises an error, the MCP server can't be reached or answers 404, the model asks for more than 4 rounds, the whole question takes longer than 12 seconds, or the final text is empty after cleanup.

#### Scenario: Bedrock error
- **WHEN** Converse raises `ThrottlingException`
- **THEN** the assistant reports failure `bedrock_error`

#### Scenario: MCP server unreachable
- **WHEN** connecting to the MCP URL fails, or the server answers 404 because the key is wrong
- **THEN** the assistant reports failure `mcp_error` and the model is not called

#### Scenario: Too many rounds
- **WHEN** the model asks for a tool in each of 4 rounds
- **THEN** the assistant stops without a 5th model request and reports failure `too_many_rounds`

#### Scenario: Too slow
- **WHEN** the clock passes 12 seconds since the question started, before the model gives a final answer
- **THEN** no further model or tool call is made and the assistant reports failure `timeout`

#### Scenario: Empty answer
- **WHEN** the model's final text is "<thinking>hmm</thinking>"
- **THEN** the assistant reports failure `empty_answer`

### Requirement: Daily budget
The assistant SHALL answer at most `ASK_AGENT_DAILY_LIMIT` questions (default 100) per account per local day in the household time zone. A question counts when the assistant starts on it. Once the limit is reached, the assistant SHALL report failure `over_budget` without calling the model or the MCP server.

#### Scenario: Under the limit
- **WHEN** the limit is 2 and 1 question has been answered today
- **THEN** the next question is answered by the assistant and the day's count becomes 2

#### Scenario: Limit reached
- **WHEN** the limit is 2 and 2 questions have been answered today
- **THEN** the next question reports `over_budget` and Converse is not called

#### Scenario: New day
- **WHEN** the limit was reached yesterday (household time) and a question is asked today
- **THEN** the assistant answers it

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
