# Tasks

Backend commands run from `backend/`, PWA commands from `pwa/`.

## 1. Hand-entered names and categories (fridge-inventory)

- [x] 1.1 Write failing tests in `tests/test_manual_items.py` for "Blank or long name", "Name at the limit" and "Unknown category" (against `clean_name()` / `check_category()`). Run `uv run pytest tests/test_manual_items.py` and verify they fail because the functions don't exist
- [x] 1.2 Implement `InvalidItem`, `clean_name()` and `check_category()` (using `analysis.CATEGORIES`) in `fridgesense/inventory.py` to make 1.1 pass

## 2. Add an item by hand (fridge-inventory)

- [x] 2.1 Write failing tests for "Add a new item", "Add to an existing item", "Add to an item that ran out", and the stock-age scenario "Item added by hand" (in `tests/test_stock_age.py`). Verify they fail because `add_item` doesn't exist
- [x] 2.2 Implement `add_item(table, account_id, name, category, quantity, now)` with `stock_age`, an `item_added` log event and validation through 1.2. Verify 2.1 passes

## 3. Edit an item by hand (fridge-inventory)

- [x] 3.1 Write failing tests for "Set a count with a category for a new item" (in `tests/test_inventory_rules.py`), and confirm the existing "Correct a count" / "Add an item by hand" tests still pass unchanged
- [x] 3.2 Add an optional `category` to `set_quantity` to make 3.1 pass
- [x] 3.3 Write failing tests for "Rename an item", "Change only the capitalization", "Change only the category" and "Rename and recount together". Verify they fail because `edit_item` doesn't exist
- [x] 3.4 Implement `edit_item(table, account_id, key, quantity=None, name=None, category=None, now)`: same-key `put`, or a rename transaction (`Put` with `attribute_not_exists` + `Delete` with `attribute_exists`) that carries over `first_seen_at`, `stocked_at` and `peak_quantity`, plus an `item_edited` log event. Verify 3.3 passes
- [x] 3.5 Write failing tests for "Rename onto another item" and "Edit an unknown item". Then add `ItemExists` and `ItemNotFound`, map them from `TransactionConflict.reasons`, and verify they pass

## 4. Delete an item by hand (fridge-inventory)

- [x] 4.1 Write failing tests for "Delete an item", "Delete an out-of-stock item", "Delete an unknown item", "Delete leaves history alone" and "Item comes back after delete"
- [x] 4.2 Implement `delete_item(table, account_id, key)` as a conditional delete raising `ItemNotFound`, with an `item_deleted` log event. Verify 4.1 passes
- [x] 4.3 Refactor the shared item-row building in `set_quantity`, `edit_item` and `add_item` with `uv run pytest` green, then run `uv run ruff check src tests`

## 5. HTTP routes (inventory-api)

- [x] 5.1 Write failing tests in `tests/test_api_writes.py` for "Add over HTTP", "Add to an existing item over HTTP" and "Bad add body" (all six bodies, with their exact error strings). Verify they fail with 404 (route missing)
- [x] 5.2 Add `@route("POST", "/api/items", write=True)` in `handlers/api.py`, mapping `InvalidItem` to 400 with its message. Verify 5.1 passes
- [x] 5.3 Write failing tests for "Rename over HTTP", "Key with spaces", "Rename clash over HTTP", "Rename unknown item over HTTP" and "Bad edit fields". Keep the existing quantity-only test as "Quantity only, as before"
- [x] 5.4 Extend `put_item` to read optional `name` and `category` and call `edit_item` (or `set_quantity` when only `quantity`, or `quantity` + `category`, is given for a new key), mapping `ItemExists` → 409 `item exists` and `ItemNotFound` → 404 `not found`. Verify 5.3 passes
- [x] 5.5 Write failing tests for "Delete over HTTP", "Delete unknown item over HTTP" and "Delete without a token"
- [x] 5.6 Add `@route("DELETE", "/api/items/{key}", write=True)`. Verify 5.5 passes
- [x] 5.7 Write failing tests for "Viewer cannot add or delete items", and confirm "Viewer write refused" and "Viewer reads" still pass. They should pass once 5.2 and 5.6 are in, because the routes are marked `write=True`. If they pass immediately, check the test asserts that butter is absent and eggs is still present
- [x] 5.8 Run `uv run pytest` and `uv run ruff check src tests`, all green

## 6. PWA client and categories (inventory-app)

- [x] 6.1 Write failing tests in `src/api/client.test.ts` for `addItem` (POST `/api/items` body), `editItem` (PUT, URL-encoded key, only the fields passed) and `deleteItem` (DELETE, encoded key). Run `npx vitest run src/api/client.test.ts` and verify they fail
- [x] 6.2 Implement `addItem`, `editItem` and `deleteItem` in `src/api/client.ts`, with `setQuantity` delegating to `editItem`. Add a `src/categories.ts` `CATEGORIES` list matching `analysis.CATEGORIES`, with a test pinning its values. Verify 6.1 passes
- [x] 6.3 Update `fakeApi` in `src/test-utils.tsx` with the three methods

## 7. Add item on the Fridge screen (inventory-app)

- [x] 7.1 Write failing tests in `src/screens/Fridge.test.tsx` for "Add butter", "Blank name", "Add from an empty fridge", "Add fails" and the updated "Empty fridge" text
- [x] 7.2 Implement the "Add item" button (under the summary card and in the empty state) and `AddItemSheet` (Name, Category select defaulting to Other, Quantity stepper min 1, inline API error). Verify 7.1 passes

## 8. Edit and remove on the Fridge screen (inventory-app)

- [x] 8.1 Write failing tests for "Rename and recategorize" (payload has only the changed `name` / `category` plus `quantity`), "Name clash", "Remove an item" and "Remove cancelled". Confirm "Fix a quantity" still sends exactly `{"quantity": 12}`
- [x] 8.2 Replace `QuantityEditor` with `ItemEditor` (name, category, stepper, Save, "Remove item" with an in-sheet "Remove <name>?" confirm), handling a 409 inline as "You already have <name>.". Verify 8.1 passes
- [x] 8.3 Write failing tests in `src/DemoMode.test.tsx` for "No Add item for viewers", and update "No edits on Fridge" to also assert that no `DELETE` is sent. Then hide Add item for viewers and verify they pass
- [x] 8.4 Refactor the shared form fields between `AddItemSheet` and `ItemEditor` with `npx vitest run` green

## 9. Local mock and wrap-up

- [x] 9.1 Add `POST /items`, `PUT /items/:key` (name, category, quantity, 409 on clash) and `DELETE /items/:key` to `scripts/mock-api.ts`, then check the add/rename/remove flow by hand in the dev preview
- [x] 9.2 Run the full suite and linters green: `cd backend && uv run pytest && uv run ruff check src tests`, `cd pwa && npm test && npm run lint` (if a lint script exists), `cd infra && npm test` (no infra change expected; confirm it still passes)
- [x] 9.3 Add a friction-log entry only if an AWS/CDK step actually caused friction
