# Spec Delta

## Purpose

Keeps a running count of what is in the fridge, built from the changes seen at each door opening, so front ends can answer "do I have milk?" without looking at footage.

## ADDED Requirements

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
