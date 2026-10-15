# Spec Delta

## ADDED Requirements

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
Setting an item's quantity SHALL store exactly that non-negative whole number and `last_changed_at` = now, creating the item (category `other`) if it does not exist yet.

#### Scenario: Correct a count
- **WHEN** `eggs` has quantity 18 and the quantity is set to 12
- **THEN** `eggs` has quantity 12 and `last_changed_at` is the time of the correction

#### Scenario: Add an item by hand
- **WHEN** the quantity of `butter` is set to 1 and there is no `butter` item
- **THEN** an item `butter` exists with quantity 1 and category `other`
