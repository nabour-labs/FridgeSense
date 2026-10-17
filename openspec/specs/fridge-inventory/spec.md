# fridge-inventory Specification

## Purpose
Keeps a running count of what is in the fridge, built from the changes seen at each door opening, so front ends can answer "do I have milk?" without looking at footage.

## Requirements

### Requirement: Confident changes update the inventory
For each change in an analysis with confidence of 0.7 or more, the system SHALL add the quantity for an added item and subtract it for a removed item, keyed by the item's normalized name (trimmed, lower case, inner spaces collapsed), under the account.

#### Scenario: New item added
- **WHEN** an analysis adds `{"item": " Whole  Milk ", "category": "dairy", "quantity": 1, "confidence": 0.9}` and the inventory has no milk
- **THEN** the inventory has `whole milk` with `quantity = 1`, `category = "dairy"`, display name `Whole Milk`, and `last_changed_at` = the door event's `closed_at`

#### Scenario: Existing item added again
- **WHEN** the inventory has `eggs` with quantity 6 and an analysis adds 12 eggs with confidence 0.86
- **THEN** `eggs` has quantity 18

#### Scenario: Item removed
- **WHEN** the inventory has `chocolate bar` with quantity 2 and an analysis removes 1 with confidence 0.8
- **THEN** `chocolate bar` has quantity 1

#### Scenario: Removing more than is known
- **WHEN** the inventory has `soda can` with quantity 1 and an analysis removes 3 with confidence 0.9
- **THEN** `soda can` has quantity 0 (never negative) and stays listed

#### Scenario: Removing an unknown item
- **WHEN** an analysis removes `yogurt` with confidence 0.9 and the inventory has no yogurt
- **THEN** no inventory item is created and the change is still recorded on the door event

### Requirement: Unsure changes wait for confirmation
Changes with confidence below 0.7 SHALL NOT change the inventory. The system SHALL save each one as a pending change with the door event, item, category, direction (`added` or `removed`), quantity and confidence.

#### Scenario: Low-confidence item
- **WHEN** an analysis removes `{"item": "chocolate bar", "quantity": 1, "confidence": 0.62}`
- **THEN** the inventory is unchanged and one pending change exists for `chocolate bar`, `removed`, quantity 1, confidence 0.62, linked to the door event

#### Scenario: Exactly at the cutoff
- **WHEN** a change has confidence 0.7
- **THEN** it updates the inventory and is not pending

### Requirement: Each door event's changes are saved once
The system SHALL store the applied and pending changes on the door event, set its `status` to `"done"`, and apply each door event's changes to the inventory at most once, even if the save step runs again.

#### Scenario: Door event completed
- **WHEN** an analysis with one confident and one unsure change is saved
- **THEN** the door event has `status = "done"`, `changes` lists both with an `applied` flag, and `pending_count = 1`

#### Scenario: Save step retried
- **WHEN** the save step runs twice for the same door event
- **THEN** inventory quantities change only once and the second run reports `already_saved`

#### Scenario: Nothing changed
- **WHEN** an analysis reports no added and no removed items
- **THEN** the door event has `status = "done"` with an empty `changes` list, and the inventory is unchanged

### Requirement: Confirming a pending change applies it
Confirming a pending change SHALL apply it to the inventory the same way as a confident change (normalized name, quantity never below 0, no item created by removing an unknown one), optionally with a corrected item name and quantity. It SHALL then delete the pending change and mark that change `applied` on its door event, decreasing the door event's `pending_count`.

#### Scenario: Confirm as reported
- **WHEN** a pending change removes 1 `chocolate bar` and the inventory has 2, and it is confirmed without corrections
- **THEN** `chocolate bar` has quantity 1, the pending change no longer exists, and on its door event that change has `applied = true` and `pending_count` went from 1 to 0

#### Scenario: Confirm with a correction
- **WHEN** a pending change adds 1 `bottle`, and it is confirmed with `{"item": "Oat Milk", "quantity": 2}`
- **THEN** the inventory has `oat milk` with quantity 2 and display name `Oat Milk`, and the door event's change shows item `oat milk`, quantity 2, `applied = true`

#### Scenario: Confirm a removal of an unknown item
- **WHEN** a pending change removes `yogurt` and the inventory has no yogurt
- **THEN** no item is created, and the pending change is deleted and marked applied

### Requirement: Rejecting a pending change discards it
Rejecting a pending change SHALL delete it without touching the inventory, mark that change `rejected` on its door event, and decrease the door event's `pending_count`.

#### Scenario: Reject
- **WHEN** a pending change adds 1 `chocolate bar` and it is rejected
- **THEN** the inventory is unchanged, the pending change no longer exists, and on the door event that change has `rejected = true` and `pending_count` is 0

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

### Requirement: Concurrent inventory writes keep every change
Every inventory write (saving a door event's changes, confirming a pending change, setting a count, adding an item by hand, editing or renaming an item) SHALL only take effect if the item is still as it was when the write read it. If another write changed or deleted the item in between, the write SHALL read the item again and apply its own change to the new state, so no change is lost and a deleted item is not brought back by an older read. All other effects of the write (door event status, pending change removal) SHALL still happen together with the item write, exactly once.

#### Scenario: Two concurrent deltas both applied
- **WHEN** `milk` has quantity 2, door event A adds 1 milk and door event B adds 2 milk, both with confidence 0.9, and B is saved after A read `milk` but before A wrote it
- **THEN** `milk` has quantity 5 and both door events have status `done`

#### Scenario: Door event saved while a pending change is confirmed
- **WHEN** `eggs` has quantity 6, a pending change removing 2 eggs is confirmed, and a door event adding 6 eggs is saved after the confirmation read `eggs` but before it wrote it
- **THEN** `eggs` has quantity 10 and the pending change is gone

#### Scenario: Adding by hand while a door event is saved
- **WHEN** `butter` has quantity 1, 2 butter are added by hand, and a door event adding 1 butter is saved after the hand add read `butter` but before it wrote it
- **THEN** `butter` has quantity 4

#### Scenario: An edit racing a delete
- **WHEN** `yogurt` exists with quantity 3, it is edited to `{"quantity": 5}`, and `yogurt` is deleted after the edit read it but before the edit wrote it
- **THEN** the edit is refused as not found and there is no `yogurt` item

#### Scenario: A rename racing a delete
- **WHEN** `bottle` exists, it is edited to `{"name": "Oat Milk"}`, and `bottle` is deleted after the edit read it but before the edit wrote it
- **THEN** the edit is refused as not found and there is neither a `bottle` nor an `oat milk` item

#### Scenario: Setting a count racing a door event
- **WHEN** `cheese` has quantity 1 and peak 1, its count is set to 4, and a door event adding 5 cheese is saved after the set read `cheese` but before it wrote it
- **THEN** `cheese` has quantity 4 and `peak_quantity = 6` (the door event's peak is kept)
