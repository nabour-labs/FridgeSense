## ADDED Requirements

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
- **WHEN** `cheese` has quantity 1 and peak 1, its count is set to 4, and a door event adding 2 cheese is saved after the set read `cheese` but before it wrote it
- **THEN** `cheese` has quantity 4 and `peak_quantity = 4`
