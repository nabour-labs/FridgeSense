# Tasks

## 1. API: day range and pages (inventory-api)

- [x] 1.1 Write failing tests in `tests/test_api_events_page.py` for "One day", "Pages", "Last page exactly full" and "Bad range or page", and update "Range limit" to expect `next: null`; run `uv run pytest tests/test_api_events_page.py tests/test_api_reads.py` and verify they fail for the right reason
- [x] 1.2 Implement `from`, `to`, `limit`, `cursor` and `next` in `get_events` to make 1.1 pass

## 2. API: delete (inventory-api)

- [x] 2.1 Write failing tests for "Delete", "Unknown event" and "Viewer delete refused"; verify they fail with 404/405-style "not found" routing
- [x] 2.2 Add `inventory.delete_door_event()` and `@route("DELETE", "/api/events/{id}", write=True)` to make 2.1 pass; run `uv run ruff check src tests`

## 3. PWA client

- [x] 3.1 Write failing tests in `api/client.test.ts`: `eventsOn(from, to, 10, cursor)` GETs `/api/events?from=…&to=…&limit=10&cursor=…`, and `deleteEvent(id)` sends DELETE to `/api/events/<id>`
- [x] 3.2 Add `eventsOn` and `deleteEvent` to `ApiClient`, the `Api` type and `fakeApi()` to make 3.1 pass

## 4. Activity screen (inventory-app)

- [x] 4.1 Update `screens/Activity.test.tsx` to the paged API and write failing tests for "Today by default", "Pick a day", "Older and newer pages", "Single page", "No door openings", "Delete an opening", "Cancel delete" and "Viewer can't delete"
- [x] 4.2 Implement the day picker, pager and delete sheet in `screens/Activity.tsx` to make 4.1 pass

## 5. Check

- [x] 5.1 Run `uv run pytest` and `uv run ruff check src tests` in `backend/`, `npm test` and `npm run typecheck` in `pwa/`; verify all are green and report the results
- [x] 5.2 Run the PWA locally against the fake API and check Activity at phone width
