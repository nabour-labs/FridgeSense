# Design

## Context

- Items are single-table rows: `pk = ACCOUNT#<id>`, `sk = ITEM#<normalized name>`, with fields `name`, `category`, `quantity`, `first_seen_at`, `last_changed_at`, `stocked_at` and `peak_quantity`.
- `inventory.set_quantity` already backs `PUT /api/items/{key}` (quantity only). It creates a missing item with category `other` and runs `stock_age`.
- `handlers/api.py` routes with `@route(method, path, write=True)`. Write routes already return 403 to viewers, and every write returns `inventory_body(...)`.
- The API Gateway route (`ANY /api/{proxy+}`) and the CDN behavior (`ALLOW_ALL` on `/api/*`) already carry `POST` and `DELETE`, so no infra change is needed.
- PWA: `Fridge.tsx` has a `QuantityEditor` in a `Sheet`. `App.report()` treats any 409 as "no camera linked" and shows nothing, so a name clash must be handled inside the editor.
- MCP tools, Ask and stats read the `ITEM#` rows directly, so they pick up manual edits with no change.

## Goals / Non-Goals

**Goals:**
- Owner can add, rename, recategorize, recount and delete items from the Fridge screen.
- One set of inventory rules (normalization, stock age), shared by camera and manual writes.
- Old clients that send `PUT {"quantity": n}` keep working.

**Non-Goals:**
- MCP or voice write tools, an undo or audit trail, bulk import, merging items on rename.

## Decisions

1. **Extend `PUT /api/items/{key}`; add `POST /api/items` and `DELETE /api/items/{key}`.**
   - PUT with optional `name` and `category` keeps one "save the editor" call and stays backward compatible.
   - POST is separate because "add" adds to the count, while PUT sets it.
   - Alternative considered: `PATCH` with all-optional fields. It's cleaner REST, but it means a new verb, more tests and changes to the existing client for no demo benefit.

2. **POST to an existing item adds to its count and takes the new category.** That matches the day-one story ("I put 6 more eggs in") and the camera's add path (`quantity_put`). The display name stays as it was, the same way camera adds keep it. Alternative: 409 if the item exists. That would block adding milk you'd run out of (quantity 0).

3. **Rename is one DynamoDB transaction.**
   - It does `Put ITEM#<new>` with `attribute_not_exists(sk)` and `Delete ITEM#<old>` with `attribute_exists(sk)`, through the existing `FridgeTable.transact`.
   - From `TransactionConflict.reasons`, a failure on the put means `ItemExists` (409) and a failure on the delete means `ItemNotFound` (404).
   - When the new name normalizes to the same key, it's a plain `put` instead (only the display name changes).
   - The moved row copies `first_seen_at`, `stocked_at` and `peak_quantity`, then goes through `stock_age` with the new quantity.

4. **Delete is a hard delete** with a `attribute_exists(sk)` condition. A failed condition becomes `ItemNotFound` (404). Setting a count of 0 is still the way to say "out of"; delete is for things that should never have been there. Door events and pending changes keep their own copy of the item name, so nothing else needs touching.

5. **Validation lives in `inventory.py`, with the HTTP layer mapping errors.**
   - New `InvalidItem(ValueError)` carries the exact API error text, and new `ItemExists` and `ItemNotFound` exceptions sit next to `PendingNotFound`.
   - `clean_name()` = `normalize_name` plus the 1–60 length check.
   - The category check uses `analysis.CATEGORIES`. It's an exact match, with no case folding, so the API stays strict and the UI sends lower-case values.
   - `set_quantity` takes an optional `category`. `edit_item` replaces it on the PUT path. `set_quantity` stays as a thin wrapper, so its existing tests and callers don't change.

6. **Logging.** It emits `item_added`, `item_edited` (`renamed_from` when renamed) and `item_deleted` through `log_event`, the same way `quantity_set` is logged. Nothing goes on the Activity screen.

7. **PWA.**
   - `QuantityEditor` becomes `ItemEditor` (name, category `<select>`, stepper, Save, "Remove item"). A new `AddItemSheet` reuses the same form fields.
   - The category list is a `CATEGORIES` constant in `pwa/src/categories.ts`, mirroring the backend list, with labels from `titleCase`.
   - Remove asks for confirmation inside the same sheet ("Remove Oat Milk?" with Remove / Cancel). It doesn't use `window.confirm`, which is ugly in an installed PWA and awkward to test.
   - The editor catches `ApiError` 409 itself and shows "You already have <name>.". Any other `ApiError` shows its message inline, and the rest go to `report()`.
   - "Add item" is a button under the summary card, also shown in the empty state. Both are hidden for viewers.
   - `ApiClient` gains `addItem`, `editItem` and `deleteItem`. `setQuantity` stays for compatibility, implemented as `editItem(key, {quantity})`.
   - `scripts/mock-api.ts` handles the new routes.

## Risks / Trade-offs

- **The camera and the user can both write.** A door event saved between the editor opening and Save gets overwritten by the hand-set quantity. That's acceptable for a single-user demo: the user is correcting what they see.
- **Hard delete can't be undone.** The confirmation step is the only guard. There's no soft delete, which keeps the rule "no item" = "no record".
- **Rename clash is refused, not merged.** That's simpler and safer. The user can delete the duplicate first. Merging can come later.
- **Mirrored category lists** (Python and TS) can drift. A PWA test pins the list, and the API returns 400 `unknown category` if they drift, so the failure is visible, not silent.
- **Renaming an item the camera keeps naming wrongly** ("bottle") doesn't teach Nova anything. The next door event may still say "bottle". The existing custom instructions on the Config screen are the tool for that.

## Test strategy

- **Unit (pytest, moto DynamoDB via the existing `aws` fixture)** in a new `backend/tests/test_manual_items.py`:
  - add (new, existing, restock from 0, stock age)
  - edit (rename, same-key rename, category only, rename + quantity, clash, unknown)
  - delete (in stock, at 0, unknown, history untouched, re-created after delete)
  - name and category validation
  - Extend `test_stock_age.py` with "Item added by hand", and `test_inventory_rules.py` with "Set a count with a category for a new item".
- **Contract (pytest, in-process API handler)** in `test_api_writes.py`, using the existing `call` / `sign_in` helpers:
  - `POST /api/items`, `PUT` with name/category/clash/404/bad fields, `DELETE` 200/404/401, URL-encoded keys
  - viewer 403 on POST and DELETE
  - the existing "quantity only" test stays as the compatibility check
- **Component (Vitest + Testing Library, `fakeApi`)** in `Fridge.test.tsx` and `DemoMode.test.tsx`:
  - add flow, blank name, add from empty, add error inline
  - rename + recategorize payload (only changed fields), 409 message, remove confirm/cancel
  - no Add item / no editor for viewers
  - `client.test.ts` covers the three new client methods' method, URL and body
- **Fixtures and stubs:** no Ring, Bedrock or new fixture files. DynamoDB comes from moto, and the PWA uses `fakeApi`. No live AWS.
