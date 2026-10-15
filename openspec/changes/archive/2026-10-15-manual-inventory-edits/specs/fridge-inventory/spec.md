# Spec Delta

## ADDED Requirements

### Requirement: Adding an item by hand
Adding an item by hand with a name, a category and a quantity of 1 or more SHALL create the item under its normalized name, with that display name, category and quantity, and `first_seen_at` = `last_changed_at` = now. If the item already exists, its quantity SHALL go up by the given amount, its category SHALL become the given one, and its display name SHALL stay as it was.

#### Scenario: Add a new item
- **WHEN** there is no butter and `{"name": " Salted  Butter ", "category": "dairy", "quantity": 2}` is added at `2026-10-16T09:00:00Z`
- **THEN** the inventory has `salted butter` with display name `Salted Butter`, category `dairy`, quantity 2, and `first_seen_at` and `last_changed_at` both `2026-10-16T09:00:00Z`

#### Scenario: Add to an existing item
- **WHEN** `eggs` exists with display name `Eggs`, quantity 4 and category `other`, and `{"name": "EGGS", "category": "dairy", "quantity": 6}` is added
- **THEN** `eggs` has quantity 10, category `dairy` and display name `Eggs`

#### Scenario: Add to an item that ran out
- **WHEN** `milk` exists with quantity 0 and `{"name": "milk", "category": "dairy", "quantity": 1}` is added
- **THEN** `milk` has quantity 1 and is in stock again

### Requirement: Renaming or recategorizing an item by hand
Editing an existing item by hand SHALL be able to set a new name, a new category, a new quantity, or any mix of them, and SHALL set `last_changed_at` = now. A new name SHALL move the item to the new name's normalized key and keep its `first_seen_at`, `stocked_at` and `peak_quantity`, unless the new quantity changes them under the stock age rules. When the new name normalizes to the same key, only the display name SHALL change. Door events and pending changes SHALL be left as they are.

#### Scenario: Rename an item
- **WHEN** `bottle` has quantity 1, category `other`, `first_seen_at = "2026-10-12T09:00:00Z"` and `stocked_at = "2026-10-12T09:00:00Z"`, and it is edited to `{"name": "Oat Milk", "category": "dairy"}`
- **THEN** there is no `bottle` item, and `oat milk` exists with display name `Oat Milk`, category `dairy`, quantity 1, `first_seen_at` and `stocked_at` still `2026-10-12T09:00:00Z`, and `last_changed_at` = the time of the edit

#### Scenario: Change only the capitalization
- **WHEN** `oat milk` has display name `oat milk` and it is edited to `{"name": "Oat Milk"}`
- **THEN** the key stays `oat milk`, the display name is `Oat Milk` and the quantity is unchanged

#### Scenario: Change only the category
- **WHEN** `kefir` has category `other` and it is edited to `{"category": "dairy"}`
- **THEN** `kefir` has category `dairy` and the same quantity and name

#### Scenario: Rename and recount together
- **WHEN** `bottle` has quantity 1 and `peak_quantity = 1`, and it is edited to `{"name": "Oat Milk", "quantity": 3}`
- **THEN** `oat milk` has quantity 3 and `peak_quantity = 3`, and there is no `bottle` item

#### Scenario: Rename onto another item
- **WHEN** both `bottle` (quantity 1) and `oat milk` (quantity 2) exist and `bottle` is edited to `{"name": "Oat Milk"}`
- **THEN** the edit is refused as a name clash, and both items are unchanged

#### Scenario: Edit an unknown item
- **WHEN** there is no `yogurt` item and it is edited to `{"name": "Greek Yogurt"}`
- **THEN** the edit is refused as not found and no item is created

### Requirement: Deleting an item by hand
Deleting an item by hand SHALL remove its record completely, whatever its quantity, so it no longer appears in stock or as "out of". Door events and pending changes that name the item SHALL be left as they are. A later change for the same name SHALL create the item fresh.

#### Scenario: Delete an item
- **WHEN** `mystery jar` has quantity 1 and is deleted
- **THEN** the inventory has no `mystery jar` item, in stock or at 0

#### Scenario: Delete an out-of-stock item
- **WHEN** `soda can` has quantity 0 and is deleted
- **THEN** the inventory has no `soda can` item

#### Scenario: Delete an unknown item
- **WHEN** there is no `yogurt` item and it is deleted
- **THEN** the delete is refused as not found and nothing changes

#### Scenario: Delete leaves history alone
- **WHEN** a door event's changes include `chocolate bar`, a pending change names `chocolate bar`, and the `chocolate bar` item is deleted
- **THEN** the door event's `changes` and the pending change are unchanged

#### Scenario: Item comes back after delete
- **WHEN** `milk` was deleted and a later door event adds 1 milk with confidence 0.9 at `2026-10-17T07:30:00Z`
- **THEN** `milk` exists with quantity 1, `first_seen_at` and `stocked_at` `2026-10-17T07:30:00Z`, and `peak_quantity = 1`

### Requirement: Hand-entered names and categories are checked
Names entered by hand SHALL be trimmed, with inner spaces collapsed, and SHALL be 1 to 60 characters long after that. Categories entered by hand SHALL be one of `dairy`, `produce`, `meat`, `seafood`, `beverage`, `snack`, `condiment`, `leftovers`, `bakery`, `frozen` or `other`. A hand edit that breaks either rule SHALL change nothing.

#### Scenario: Blank or long name
- **WHEN** an item is added or edited with name `"   "` or a 61-character name
- **THEN** the write is refused and the inventory is unchanged

#### Scenario: Name at the limit
- **WHEN** an item is added with a 60-character name
- **THEN** the item is created with that name

#### Scenario: Unknown category
- **WHEN** an item is added or edited with category `"sweets"` or `"Dairy "`
- **THEN** the write is refused and the inventory is unchanged

## MODIFIED Requirements

### Requirement: Setting a quantity by hand
Setting an item's quantity SHALL store exactly that non-negative whole number and `last_changed_at` = now, creating the item if it does not exist yet. A created item SHALL get the given category, or category `other` when none is given.

#### Scenario: Correct a count
- **WHEN** `eggs` has quantity 18 and the quantity is set to 12
- **THEN** `eggs` has quantity 12 and `last_changed_at` is the time of the correction

#### Scenario: Add an item by hand
- **WHEN** the quantity of `butter` is set to 1 and there is no `butter` item
- **THEN** an item `butter` exists with quantity 1 and category `other`

#### Scenario: Set a count with a category for a new item
- **WHEN** the quantity of `butter` is set to 1 with category `dairy` and there is no `butter` item
- **THEN** an item `butter` exists with quantity 1 and category `dairy`

### Requirement: Stock age and peak count are tracked
Every write that changes an item's quantity (a confident change, a confirmed pending change, a count set by hand, an item added by hand, or an item edited by hand) SHALL also maintain:
- `stocked_at`: set to the change time when the item goes from absent or quantity 0 to a quantity above 0; left unchanged while the quantity stays above 0; removed when the quantity becomes 0.
- `peak_quantity`: set to the new quantity when the item is restocked from absent or 0; otherwise the larger of the stored `peak_quantity` and the new quantity; removed when the quantity becomes 0.

An item stored before these fields existed SHALL be read as `stocked_at` = its `first_seen_at` and `peak_quantity` = its current quantity, until its next change writes the fields.

#### Scenario: New item
- **WHEN** an analysis for a door event closed at `2026-10-16T18:02:40Z` adds 12 `eggs` with confidence 0.9 and there are no eggs
- **THEN** `eggs` has `quantity = 12`, `stocked_at = "2026-10-16T18:02:40Z"` and `peak_quantity = 12`

#### Scenario: Adding more keeps the stock age
- **WHEN** `eggs` has quantity 2, `stocked_at = "2026-10-10T08:00:00Z"`, `peak_quantity = 12`, and a later door event adds 6 eggs
- **THEN** `eggs` has `quantity = 8`, `stocked_at` is still `"2026-10-10T08:00:00Z"` and `peak_quantity` is still 12

#### Scenario: Peak rises above the old peak
- **WHEN** `yogurt` has quantity 3 and `peak_quantity = 4`, and 2 more are added
- **THEN** `yogurt` has `quantity = 5` and `peak_quantity = 5`

#### Scenario: Running out clears both
- **WHEN** `milk` has quantity 1 with `stocked_at` and `peak_quantity` set, and an analysis removes 1 milk
- **THEN** `milk` has `quantity = 0` and neither `stocked_at` nor `peak_quantity` is stored

#### Scenario: Restock after running out
- **WHEN** `milk` has quantity 0, and a door event closed at `2026-10-17T07:30:00Z` adds 2 milk
- **THEN** `milk` has `quantity = 2`, `stocked_at = "2026-10-17T07:30:00Z"` and `peak_quantity = 2`

#### Scenario: Confirmed pending change
- **WHEN** a pending change adding 1 `butter` is confirmed at `2026-10-16T19:00:00Z` and there is no butter
- **THEN** `butter` has `stocked_at = "2026-10-16T19:00:00Z"` and `peak_quantity = 1`

#### Scenario: Count set by hand
- **WHEN** `eggs` has quantity 12, `peak_quantity = 12`, and the quantity is set to 0 by hand, then later set to 6 at `2026-10-18T10:00:00Z`
- **THEN** after the first write neither field is stored, and after the second `stocked_at = "2026-10-18T10:00:00Z"` and `peak_quantity = 6`

#### Scenario: Item added by hand
- **WHEN** there is no cheese and 2 `cheese` are added by hand at `2026-10-16T09:00:00Z`, then 3 more at `2026-10-17T09:00:00Z`
- **THEN** `cheese` has `quantity = 5`, `stocked_at = "2026-10-16T09:00:00Z"` and `peak_quantity = 5`

#### Scenario: Item saved before this change
- **WHEN** `cheese` has quantity 2 and `first_seen_at = "2026-10-12T09:00:00Z"`, with no `stocked_at` or `peak_quantity`
- **THEN** it is read as `stocked_at = "2026-10-12T09:00:00Z"` and `peak_quantity = 2`
