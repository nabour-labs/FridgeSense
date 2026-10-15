## ADDED Requirements

### Requirement: Stock age and peak count are tracked
Every write that changes an item's quantity (a confident change, a confirmed pending change, or a count set by hand) SHALL also maintain:
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

#### Scenario: Item saved before this change
- **WHEN** `cheese` has quantity 2 and `first_seen_at = "2026-10-12T09:00:00Z"`, with no `stocked_at` or `peak_quantity`
- **THEN** it is read as `stocked_at = "2026-10-12T09:00:00Z"` and `peak_quantity = 2`
