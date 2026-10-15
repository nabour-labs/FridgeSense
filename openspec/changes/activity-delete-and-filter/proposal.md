# Proposal

## Why

The Activity screen lists every door opening from the last 7 days in one long scroll. A busy fridge makes that slow to read, and there is no way to look at one day or to get rid of a false opening (for example, the door bumped while cleaning). The owner wants to pick a day, page through it, and delete an opening.

Tracks: **Ring** (door openings come from the Ring camera) and **AWS Builder** (API and DynamoDB).

## What Changes

- **Day filter on Activity**, defaulting to today in the device's time zone. The day picker can't go past today.
- **Pagination**: 10 openings per page with "Newer" and "Older" buttons and a page number.
- **Delete a door opening** (owner only): a delete button on each card asks for confirmation, then removes the opening and its unconfirmed changes. Fridge quantities stay as they are.
- **API**: `GET /api/events` gains `from`, `to`, `limit` and `cursor`, and returns `next`. A new `DELETE /api/events/{id}` write route.

## Capabilities

### Modified Capabilities

- `inventory-api`: door event listing gains a time range and pages; adds door event deletion; the read-only rule lists the new write route.
- `inventory-app`: the Activity screen gains the day filter, pages and deletion.

## Out of scope

- Undoing the inventory changes a deleted opening applied (fix quantities on the Fridge screen instead).
- Deleting a single change inside an opening, bulk delete, or undo after delete.
- Deleting the opening's stills and clip from S3: the 7-day lifecycle removes them.
- Date ranges longer than one day in the app; Stats keeps its 28-day request.

## Impact

- **Backend:** `handlers/api.py` (`get_events` parameters, new `delete_event`), `inventory.py` (`delete_door_event`). No new dependencies.
- **PWA:** `api/client.ts` (`eventsOn`, `deleteEvent`), `AppContext.tsx`, `test-utils.tsx`, `screens/Activity.tsx`.
- **AWS:** no new resources; `ANY /api/{proxy+}` already carries DELETE. Needs a Lambda deploy.
