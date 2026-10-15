# Proposal

## Why

The inventory only learns from door openings the camera sees. That leaves three gaps:

- **Day one.** The fridge is already full when the camera is turned on, so the app starts empty and stays wrong until each item happens to be taken out.
- **Mistakes.** Nova sometimes names an item wrongly or picks the wrong category. Today the app can only fix the count of an existing item (`PUT /api/items/{key}` with `{"quantity": n}`). It can't rename an item, change its category or remove it.
- **Camera offline.** While the camera is down, the user has no proper way to record what went in or out.

The app needs plain add, edit and delete for inventory items.

Tracks: **Ring** (it keeps the camera-built inventory accurate) and **Alexa+** (the MCP answers read the same inventory, so "do I have milk?" is right from day one).

## What Changes

- **Add an item by hand.** A new `POST /api/items` with `{"name", "category", "quantity"}`:
  - It creates the item, or adds to its count if the item already exists.
  - It keeps stock age (`stocked_at`, `peak_quantity`) the same way a door event does.
- **Edit an item.** `PUT /api/items/{key}` gains optional `name` and `category` fields next to `quantity`:
  - A new name renames the item and moves it to the new key, keeping its history fields.
  - Renaming onto another existing item is refused with 409.
  - Existing callers that send only `{"quantity": n}` behave exactly as before.
- **Delete an item.** A new `DELETE /api/items/{key}` removes the item completely, including from the "Out of" list. Door event history and pending changes are left alone.
- **Shared rules.** Categories must come from the same list Nova uses (`dairy`, `produce`, … `other`). Names are trimmed and limited to 60 characters. Viewer (demo) tokens get 403 on all three writes.
- **PWA Fridge screen**, for the owner only:
  - An "Add item" button opens a sheet with a name, a category picker and a quantity stepper.
  - The empty fridge state also offers "Add item", for setting up on day one.
  - Tapping an item opens an editor with name, category, quantity and a "Remove item" button that asks for confirmation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `fridge-inventory`: adds manual add, rename/recategorize and delete rules, and extends "Setting a quantity by hand".
- `inventory-api`: adds `POST /api/items` and `DELETE /api/items/{key}`, extends `PUT /api/items/{key}`, and adds both new routes to the viewer read-only list.
- `inventory-app`: the Fridge screen gains Add item, a full item editor and Remove item; demo mode hides them.

## Out of scope

- **Voice or MCP write tools**, such as "Alexa, I added milk". The MCP server stays read-only.
- **A change log or undo** for manual edits. Edits don't show up on the Activity screen and are only logged.
- **Bulk import**, such as a list, receipt or photo of the whole fridge, and barcode scanning.
- **Merging two items** when a rename collides. The user gets a 409 and can delete one item first.
- **Expiry dates** or other new item fields.

## Impact

- **Backend:** `backend/src/fridgesense/inventory.py` gains `add_item`, `edit_item` and `delete_item`, and shares a category check with `analysis.CATEGORIES`. `handlers/api.py` gains two routes, and `PUT /api/items/{key}` takes the new fields. No new dependencies.
- **PWA:** `screens/Fridge.tsx` (add and edit sheets, remove confirmation), `api/client.ts` (`addItem`, `editItem`, `deleteItem`), and `scripts/mock-api.ts` so the local mock supports the new routes.
- **AWS:** no new resources and no IAM change. The existing `ANY /api/{proxy+}` route and the CDN's `ALLOW_ALL` `/api/*` behavior already pass `POST` and `DELETE`. Shipping it needs a Lambda and site deploy only.
- **MCP and Ask:** no code change. They read the same `ITEM#` records, so manual edits show up in their answers right away.
