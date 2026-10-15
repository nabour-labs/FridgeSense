# Design

## Context

- Door events are `DOOR#<opened_at ISO UTC>#<device_id>` items under the account's partition. `GET /api/events?days=n` queries them newest first. Pending changes are `PENDING#…` items that carry `door_sk`.
- The Activity screen polls `api.events(7)` every 10 s through `useLoad`. Stats calls `api.events(28)`.
- `/api/{proxy+}` sends every method to the API Lambda, and `@route(..., write=True)` already refuses viewers with 403.

## Decisions

### The browser sends the day as a UTC range
"Today" is the device's day. The PWA computes local midnight to the next local midnight and sends both as ISO instants: `from` (inclusive) and `to` (exclusive). The API needs no time zone. Because sort keys are `DOOR#<iso>#<device>`, the key range `DOOR#<from>` to `DOOR#<to>` is exactly `[from, to)`.

### Cursor pages, not offsets
With `limit`, the API returns at most `limit` events plus `next`, the id of the last one, when older events remain. The next page passes it as `cursor` and gets events strictly older than it. DynamoDB has no offset, so the PWA keeps a stack of cursors for "Newer". Page size is 10. Without `limit`, every event in range is returned and `next` is null, so Stats is unchanged.

### Delete removes the event and its pending rows only
`DELETE /api/events/{id}` deletes the `DOOR#` item and every `PENDING#` item whose `door_sk` matches. It does not undo applied changes: the user asked to keep stock as is. Stills expire with the S3 lifecycle.

### Confirm before deleting
Deleting can't be undone, so the card's delete button opens a sheet with "Delete" and "Cancel". After a delete the screen reloads the current page.

## Risks

- A delete between page loads can shift items across pages. Acceptable for a single-user demo.

## Test strategy

- **Backend unit/integration (moto):** `tests/test_api_events_page.py` covers range, limit and cursor paging, validation and delete through `api.handler`, using the existing `link_account()`/`sign_in()` helpers. No live AWS.
- **PWA (Vitest + Testing Library):** `client.test.ts` checks the URLs and methods; `Activity.test.tsx` checks the default day, day change, paging, delete with confirmation, and that viewers see no delete button. The API is `fakeApi()`.
