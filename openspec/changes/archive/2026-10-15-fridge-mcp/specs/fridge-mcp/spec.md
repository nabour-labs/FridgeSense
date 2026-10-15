# Spec Delta

## Purpose

Lets voice assistants such as Alexa+ and other MCP clients answer questions about the fridge (what is in it, whether an item is there, when it was last opened and how often), through a read-only MCP server over Streamable HTTP.

## ADDED Requirements

### Requirement: Streamable HTTP MCP endpoint behind a URL key
The system SHALL serve a stateless MCP server over Streamable HTTP at `/mcp/<key>`, answering JSON-RPC with `application/json`, and SHALL accept protocol versions 2025-11-25 and 2025-03-26 at `initialize`. A request whose `<key>` does not equal the configured `mcp_key`, or any request when no key is configured, SHALL get 404 without reaching the MCP server.

#### Scenario: Initialize with 2025-11-25
- **WHEN** a client POSTs `{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}` to `/mcp/<correct key>` with `Accept: application/json, text/event-stream`
- **THEN** the response is 200 JSON with `result.protocolVersion` `"2025-11-25"`, `result.serverInfo.name` `"fridgesense"` and a `tools` capability

#### Scenario: Older client version
- **WHEN** the `initialize` request asks for `protocolVersion` `"2025-03-26"`
- **THEN** the response is 200 and `result.protocolVersion` is `"2025-03-26"`

#### Scenario: Wrong key
- **WHEN** a request goes to `/mcp/not-the-key`
- **THEN** the response is 404 and no tool runs

#### Scenario: No key configured
- **WHEN** `mcp_key` is missing or empty in the app secret
- **THEN** every `/mcp/<anything>` request gets 404

#### Scenario: Request through API Gateway
- **WHEN** the request arrives from API Gateway with `Host: <id>.execute-api.us-east-1.amazonaws.com`, on the first invocation and again on a second warm invocation
- **THEN** both get 200 (no host rejection and no failure on reuse)

### Requirement: Four read-only tools
`tools/list` SHALL list exactly `find_item`, `get_inventory`, `fridge_activity` and `last_opened`. Each tool SHALL have `annotations.readOnlyHint` true, `destructiveHint` false and `idempotentHint` true, an `outputSchema`, and a description saying when to use it.

#### Scenario: Tool list
- **WHEN** a client calls `tools/list` after initializing
- **THEN** the four tools are listed with those annotations and each has an `outputSchema`

### Requirement: Find an item
`find_item(name)` SHALL return `{"query", "in_fridge", "total_count", "matches": [{"name", "count", "last_changed_at", "minutes_ago"}]}`. It matches inventory items by normalized name, ignoring case, a trailing plural "s" or "es", and as a whole word inside longer names. `in_fridge` is true only when `total_count` is above 0.

#### Scenario: Do I have milk?
- **WHEN** the inventory has `milk` with quantity 1, changed 12 minutes ago, and `find_item` is called with `"Milk"`
- **THEN** the result is `in_fridge: true`, `total_count: 1` and one match `{"name": "milk", "count": 1, "minutes_ago": 12, …}`

#### Scenario: Plural and partial names
- **WHEN** the inventory has `egg` (6) and `whole milk` (1), and `find_item` is called with `"eggs"` and then with `"milk"`
- **THEN** `"eggs"` matches `egg` with `total_count: 6`, and `"milk"` matches `whole milk`

#### Scenario: Several matches
- **WHEN** the inventory has `whole milk` (1) and `oat milk` (2), and `find_item` is called with `"milk"`
- **THEN** both are matches and `total_count` is 3

#### Scenario: Run out
- **WHEN** `soda can` has quantity 0 and `find_item` is called with `"soda"`
- **THEN** the result is `in_fridge: false`, `total_count: 0` and the match lists `soda can` with count 0, so the answer can say it ran out

#### Scenario: Never seen
- **WHEN** nothing matches `"caviar"`
- **THEN** the result is `in_fridge: false`, `total_count: 0` and `matches: []` (not an error)

### Requirement: What is in the fridge
`get_inventory(category?)` SHALL return `{"total_items", "items": [{"name", "category", "count"}], "pending_count"}` for items with quantity above 0, sorted by category then name, filtered to one category when `category` is given (case-insensitive).

#### Scenario: Whole fridge
- **WHEN** the inventory has eggs (6, dairy), apple (3, produce) and soda can (0, beverage), and one change is pending
- **THEN** `items` lists eggs and apple (not soda can), `total_items` is 2 and `pending_count` is 1

#### Scenario: One category
- **WHEN** `get_inventory` is called with `category` `"Dairy"`
- **THEN** only dairy items are listed

### Requirement: Fridge activity
`fridge_activity(period)` with `period` `"today"` or `"week"` SHALL return `{"period", "opens", "average_open_seconds", "last_opened_at", "busiest_hour"}` computed from door events in the configured time zone. "today" starts at local midnight; "week" covers the last 7 days including today. `average_open_seconds` and `busiest_hour` are null without opens.

#### Scenario: Opens today
- **WHEN** the time zone is America/Toronto, it is 20:00 local, and there were door events today at 08:10 (20 s), 08:40 (30 s) and 18:05 (40 s), plus one yesterday
- **THEN** `fridge_activity("today")` returns `opens: 3`, `average_open_seconds: 30`, `busiest_hour: 8` and `last_opened_at` = the 18:05 event's time

#### Scenario: No opens
- **WHEN** there are no door events this week
- **THEN** `fridge_activity("week")` returns `opens: 0`, `average_open_seconds: null` and `busiest_hour: null`

#### Scenario: Unknown period
- **WHEN** `period` is `"year"`
- **THEN** the tool call fails validation (an error result naming the allowed values) and no table query runs

### Requirement: Last opening
`last_opened()` SHALL return the most recent door event as `{"opened_at", "minutes_ago", "duration_s", "added": [{"name", "count"}], "removed": [{"name", "count"}], "unsure_count"}`, counting only applied changes as added or removed and pending ones as `unsure_count`. With no door events it SHALL return `{"opened_at": null}` with empty lists.

#### Scenario: Milk just went in
- **WHEN** the last door event, 3 minutes ago for 18 s, applied "+1 milk" and has one pending change
- **THEN** the result is `minutes_ago: 3`, `duration_s: 18`, `added: [{"name": "milk", "count": 1}]`, `removed: []` and `unsure_count: 1`

#### Scenario: Never opened
- **WHEN** there are no door events
- **THEN** the result has `opened_at: null`, `minutes_ago: null`, `added: []` and `removed: []`

### Requirement: Tools explain a missing camera link
When no Ring account is linked, every tool SHALL return an error result (`isError: true`) whose text says no camera is linked yet, instead of an empty answer.

#### Scenario: Not linked
- **WHEN** the token store is empty and `find_item("milk")` is called
- **THEN** the result has `isError: true` and its text contains "No camera is linked"
