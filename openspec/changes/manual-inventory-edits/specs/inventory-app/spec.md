# Spec Delta

## ADDED Requirements

### Requirement: Add an item from the Fridge screen
For the owner, the Fridge screen SHALL show an "Add item" button that opens a sheet with a Name field, a Category picker (default Other) and a Quantity stepper (default 1, minimum 1). Saving SHALL send `POST /api/items`, close the sheet and show the returned list. Save SHALL stay disabled while the name is blank.

#### Scenario: Add butter
- **WHEN** the owner taps "Add item", types "Butter", picks Dairy, sets the quantity to 2 and taps Save
- **THEN** `POST /api/items` is sent with `{"name": "Butter", "category": "dairy", "quantity": 2}`, the sheet closes and the Dairy group shows Butter ×2

#### Scenario: Blank name
- **WHEN** the Add item sheet is open and the name is empty or only spaces
- **THEN** Save is disabled and no request is sent

#### Scenario: Add from an empty fridge
- **WHEN** the owner signs in and there are no items
- **THEN** the empty-fridge message also shows an "Add item" button that opens the Add item sheet

#### Scenario: Add fails
- **WHEN** `POST /api/items` answers 400 `{"error": "unknown category"}`
- **THEN** the sheet stays open, shows "unknown category" and the list is unchanged

### Requirement: Edit or remove an item from the Fridge screen
For the owner, tapping an item SHALL open an editor with its Name, Category and Quantity filled in. Save SHALL send `PUT /api/items/{key}` with `quantity`, plus `name` and `category` only when they changed. "Remove item" SHALL ask "Remove <name>?" first, and only on confirm send `DELETE /api/items/{key}`. Both SHALL show the returned list.

#### Scenario: Rename and recategorize
- **WHEN** the owner taps Bottle (other, ×1), changes the name to "Oat Milk" and the category to Dairy, and saves
- **THEN** `PUT /api/items/bottle` is sent with `{"quantity": 1, "name": "Oat Milk", "category": "dairy"}`, the sheet closes and the Dairy group shows Oat Milk ×1

#### Scenario: Name clash
- **WHEN** the owner renames Bottle to "Oat Milk" and the API answers 409 `{"error": "item exists"}`
- **THEN** the editor stays open and shows "You already have Oat Milk." and the list is unchanged

#### Scenario: Remove an item
- **WHEN** the owner taps Mystery Jar, taps "Remove item" and confirms "Remove Mystery Jar?"
- **THEN** `DELETE /api/items/mystery%20jar` is sent, the sheet closes and Mystery Jar is no longer listed, in stock or under "Out of"

#### Scenario: Remove cancelled
- **WHEN** the owner taps "Remove item" and then cancels the confirmation
- **THEN** no `DELETE` request is sent and the editor is still open

## MODIFIED Requirements

### Requirement: Fridge screen
The Fridge screen SHALL show a summary card with the number of in-stock items, when the inventory last changed and, when changes are pending, a link to Review. It SHALL list in-stock items grouped by category with an emoji icon, name, quantity and when each last changed, list items with quantity 0 in a collapsed "Out of" section, and show an illustrated message when the fridge is empty. It SHALL refresh every 10 s while the app is visible.

#### Scenario: Items by category
- **WHEN** the API returns eggs (6, dairy), milk (1, dairy) and apple (3, produce)
- **THEN** the screen shows a "Dairy" group with eggs ×6 and milk ×1 and a "Produce" group with apple ×3

#### Scenario: Out of stock
- **WHEN** soda can has quantity 0
- **THEN** it is not in its category group but appears in the "Out of" section

#### Scenario: Pending banner
- **WHEN** `pending_count` is 2
- **THEN** a link reads "2 items to confirm" and tapping it opens Review

#### Scenario: Summary card
- **WHEN** the API returns eggs (6), milk (1, last changed 2 minutes ago), apple (3) and soda can (0)
- **THEN** a "Fridge summary" region shows "3 in stock" and "Last change 2 min ago"

#### Scenario: Summary with nothing changed yet
- **WHEN** no item has a `last_changed_at`
- **THEN** the summary card shows the in-stock count and no "Last change" text

#### Scenario: Item icons from name
- **WHEN** the items are milk (dairy), apple (produce) and leftover pasta (leftovers)
- **THEN** their rows show 🥛, 🍎 and 🍝

#### Scenario: Item icon falls back to category, then a plate
- **WHEN** the items are kefir (dairy) and mystery jar (other)
- **THEN** kefir shows the dairy icon 🧀 and mystery jar shows 🍽️

#### Scenario: Empty fridge
- **WHEN** there are no items
- **THEN** the screen says the fridge is empty and that items appear after the next door opening or can be added by hand

#### Scenario: Live refresh
- **WHEN** the app is visible and 10 s pass
- **THEN** the inventory is requested again and new quantities are shown without a reload

#### Scenario: Hidden app does not poll
- **WHEN** the page is hidden
- **THEN** no further inventory requests are made until it is visible again

#### Scenario: Fix a quantity
- **WHEN** the user taps an item, changes eggs from 6 to 12 and saves
- **THEN** `PUT /api/items/eggs` is sent with `{"quantity": 12}` and the list shows eggs ×12

### Requirement: Read-only demo mode
When the session's role is `viewer`, the app SHALL show a "Demo · read-only" badge on every screen, SHALL make Fridge items not editable and hide "Add item", SHALL list pending changes on Review without Confirm, Edit or "Not right" buttons, and SHALL show "Read-only demo" without changing the screen's data if the API answers 403.

#### Scenario: Demo sign-in
- **WHEN** the user signs in with the demo passcode and the API returns `role` `"viewer"`
- **THEN** the token and role are stored, the Fridge screen is shown and a "Demo · read-only" badge is visible

#### Scenario: No edits on Fridge
- **WHEN** the role is `viewer` and the user taps eggs
- **THEN** no item editor opens and no `PUT` or `DELETE` request is sent

#### Scenario: No Add item for viewers
- **WHEN** the role is `viewer`, with items or with an empty fridge
- **THEN** no "Add item" button is shown

#### Scenario: No actions on Review
- **WHEN** the role is `viewer` and one change is pending
- **THEN** Review lists it with item, direction, quantity and confidence, and shows no Confirm, Edit or "Not right" buttons

#### Scenario: Write refused
- **WHEN** a write request answers 403
- **THEN** the app shows "Read-only demo" and the list on screen is unchanged
