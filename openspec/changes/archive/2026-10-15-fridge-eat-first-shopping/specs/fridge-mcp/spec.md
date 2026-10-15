## RENAMED Requirements

- FROM: `### Requirement: Four read-only tools`
- TO: `### Requirement: Read-only tools`

## MODIFIED Requirements

### Requirement: Read-only tools
`tools/list` SHALL list exactly `find_item`, `get_inventory`, `fridge_activity`, `last_opened`, `oldest_items` and `low_stock`. Each tool SHALL have `annotations.readOnlyHint` true, `destructiveHint` false and `idempotentHint` true, an `outputSchema`, and a description saying when to use it.

#### Scenario: Tool list
- **WHEN** a client calls `tools/list` after initializing
- **THEN** the six tools are listed with those annotations and each has an `outputSchema`

## ADDED Requirements

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
