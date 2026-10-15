# fridge-mcp Specification

## Purpose
Lets voice assistants such as Alexa+ and other MCP clients answer questions about the fridge (what is in it, whether an item is there, when it was last opened and how often), through a read-only MCP server over Streamable HTTP.

## Requirements

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

### Requirement: Read-only tools
`tools/list` SHALL list exactly `find_item`, `get_inventory`, `fridge_activity`, `last_opened`, `oldest_items` and `low_stock`. Each tool SHALL have `annotations.readOnlyHint` true, `destructiveHint` false and `idempotentHint` true, an `outputSchema`, and a description saying when to use it.

#### Scenario: Tool list
- **WHEN** a client calls `tools/list` after initializing
- **THEN** the six tools are listed with those annotations and each has an `outputSchema`

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

### Requirement: Oldest items first
`oldest_items(category?, limit?)` SHALL return `{"items": [{"name", "category", "count", "in_fridge_since", "days_in_fridge"}], "skipped_categories"}` for items with quantity above 0, oldest `stocked_at` first (ties by name), at most `limit` items (default 5, allowed 1 to 20). `in_fridge_since` is the item's `stocked_at` and `days_in_fridge` is the whole number of days from it to now (rounded down). Without `category`, items in the long-life categories `condiment`, `frozen` and `beverage` SHALL be left out and `skipped_categories` SHALL list those three. With `category` (case-insensitive), only that category is listed, even a long-life one, and `skipped_categories` is empty.

#### Scenario: What should I eat first?
- **WHEN** it is `2026-10-20T12:00:00Z` and the inventory has milk (1, dairy, stocked `2026-10-11T08:00:00Z`), apple (3, produce, stocked `2026-10-14T08:00:00Z`) and leftovers (1, leftovers, stocked `2026-10-20T09:00:00Z`)
- **THEN** `items` is milk (`days_in_fridge: 9`), then apple (`days_in_fridge: 6`), then leftovers (`days_in_fridge: 0`), each with its `count`, `category` and `in_fridge_since`

#### Scenario: Long-life items left out
- **WHEN** the inventory has ketchup (1, condiment, stocked 40 days ago), soda can (6, beverage, stocked 20 days ago) and eggs (6, dairy, stocked 5 days ago), and no category is given
- **THEN** only eggs is listed and `skipped_categories` is `["condiment", "frozen", "beverage"]`

#### Scenario: One category, even a long-life one
- **WHEN** `oldest_items` is called with `category` `"Condiment"` and the inventory has ketchup (1, condiment)
- **THEN** ketchup is listed and `skipped_categories` is `[]`

#### Scenario: Out-of-stock items are not listed
- **WHEN** butter has quantity 0
- **THEN** butter is not in `items`

#### Scenario: Limit
- **WHEN** eight perishable items are in stock and `oldest_items` is called with `limit` 3
- **THEN** exactly the three oldest are listed

#### Scenario: Limit out of range
- **WHEN** `limit` is 0 or 21
- **THEN** the tool call fails validation (an error result naming the allowed range) and no table query runs

#### Scenario: Item saved before stock tracking
- **WHEN** cheese (2, dairy) has no `stocked_at` and `first_seen_at = "2026-10-12T09:00:00Z"`
- **THEN** it is listed with `in_fridge_since: "2026-10-12T09:00:00Z"`

#### Scenario: Nothing perishable
- **WHEN** no item outside the long-life categories has quantity above 0
- **THEN** the result is `items: []` (not an error)

### Requirement: Shopping list from what ran out or is low
`low_stock()` SHALL return `{"ran_out": [{"name", "category", "ran_out_at", "days_ago"}], "running_low": [{"name", "category", "count", "usual_count"}]}`.
- `ran_out` lists items with quantity 0 whose `last_changed_at` is within the last 30 days, most recent first, at most 10. `ran_out_at` is `last_changed_at`; `days_ago` is whole days to now, rounded down.
- `running_low` lists items with quantity above 0 whose quantity is at most a quarter of their `peak_quantity` (`count * 4 <= peak_quantity`), sorted by name. `usual_count` is the `peak_quantity`.

#### Scenario: What do I need to buy?
- **WHEN** it is `2026-10-20T12:00:00Z`, milk has quantity 0 changed `2026-10-19T08:00:00Z`, butter has quantity 0 changed `2026-10-17T08:00:00Z`, and eggs have quantity 2 with `peak_quantity` 12
- **THEN** `ran_out` is milk (`days_ago: 1`) then butter (`days_ago: 3`), and `running_low` is `[{"name": "eggs", "category": "dairy", "count": 2, "usual_count": 12}]`

#### Scenario: Old run-outs are dropped
- **WHEN** caviar has quantity 0 and was last changed 31 days ago
- **THEN** caviar is not in `ran_out`

#### Scenario: At most ten run-outs
- **WHEN** twelve items ran out in the last 30 days
- **THEN** `ran_out` lists the ten most recent

#### Scenario: Not low yet
- **WHEN** yogurt has quantity 2 and `peak_quantity` 4, and apples have quantity 3 and `peak_quantity` 12
- **THEN** yogurt is not in `running_low` (2 × 4 > 4) and apples are (3 × 4 ≤ 12)

#### Scenario: Single item never counts as low
- **WHEN** milk has quantity 1 and `peak_quantity` 1
- **THEN** milk is not in `running_low`

#### Scenario: Nothing to buy
- **WHEN** nothing ran out in 30 days and nothing is low
- **THEN** the result is `ran_out: []` and `running_low: []` (not an error)

#### Scenario: Not linked
- **WHEN** the token store is empty and `low_stock` or `oldest_items` is called
- **THEN** the result has `isError: true` and its text contains "No camera is linked"
