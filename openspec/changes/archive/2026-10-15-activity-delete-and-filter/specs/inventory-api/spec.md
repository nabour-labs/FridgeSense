## MODIFIED Requirements

### Requirement: Viewer tokens are read-only
A token with role `viewer` SHALL be accepted on every `GET` route and SHALL be refused on every write route (`POST /api/pending/{id}/confirm`, `POST /api/pending/{id}/reject`, `PUT /api/items/{key}`, `DELETE /api/events/{id}`) with 403 `{"error": "read-only"}`, changing nothing.

#### Scenario: Viewer write refused
- **WHEN** a viewer token calls `POST /api/pending/{id}/confirm` for an existing pending change, or `PUT /api/items/milk` with `{"quantity": 2}`
- **THEN** the response is 403 `{"error": "read-only"}`, the pending change still exists and the inventory is unchanged

#### Scenario: Viewer delete refused
- **WHEN** a viewer token calls `DELETE /api/events/{id}` for an existing door event
- **THEN** the response is 403 `{"error": "read-only"}` and the event is still listed

#### Scenario: Viewer reads
- **WHEN** a viewer token calls `GET /api/inventory`, `GET /api/events` and `GET /api/pending`
- **THEN** each responds 200 with the same body an owner token gets

### Requirement: Door event listing
`GET /api/events` SHALL return `{"events": [...], "next": <id or null>}`, newest first. Each event has `id`, `opened_at`, `closed_at`, `duration_s`, `status`, `changes`, `pending_count`, and `stills`: 15-minute download links for its stored stills, or `[]` for events older than 7 days.

The range is either `days=<n>` (default 7, max 30, ending now) or `from` and `to`, ISO 8601 instants with `from` inclusive, `to` exclusive, `from` before `to` and at most 31 days apart. When `from` is given, `days` is ignored. With `limit=<n>` (1 to 50) at most `n` events are returned and `next` is the id of the last one when older events remain in the range, else null; `cursor=<id>` returns only events older than that event. Without `limit`, every event in range is returned and `next` is null.

#### Scenario: Recent event with stills
- **WHEN** a `done` door event opened 1 hour ago has 4 stored stills
- **THEN** it is listed with 4 `stills` links that download the images without any other credentials, and with its `changes`

#### Scenario: Old event
- **WHEN** a door event opened 8 days ago and `days=30`
- **THEN** it is listed with `stills: []`

#### Scenario: Range limit
- **WHEN** events exist 2 and 10 days ago and the request has no `days`
- **THEN** only the event from 2 days ago is listed and `next` is null

#### Scenario: Days out of range
- **WHEN** `days=0`, `days=31` or `days=abc`
- **THEN** the response is 400

#### Scenario: One day
- **WHEN** events opened at 03:59, 04:00, 12:00 and 03:59 the next day (UTC), and the request has `from=…T04:00:00.000Z` and `to=` 24 hours later
- **THEN** only the 12:00 and 04:00 events are listed, in that order

#### Scenario: Pages
- **WHEN** 3 events are in range and the request has `limit=2`
- **THEN** the 2 newest are listed and `next` is the id of the second; the same request with `cursor=<next>` lists only the oldest and `next` is null

#### Scenario: Last page exactly full
- **WHEN** 2 events are in range and the request has `limit=2`
- **THEN** both are listed and `next` is null

#### Scenario: Bad range or page
- **WHEN** `from=yesterday`, `from` without `to`, `to` before `from`, a range over 31 days, `limit=0`, `limit=51` or `cursor=nope`
- **THEN** the response is 400

## ADDED Requirements

### Requirement: Delete a door event
`DELETE /api/events/{id}` SHALL delete the door event and every pending change that came from it, and respond 200 `{"id": "<id>"}`. It SHALL NOT change the inventory.

#### Scenario: Delete
- **WHEN** an owner deletes an event that applied "+ milk" and has one pending change
- **THEN** the response is 200, the event is gone from `GET /api/events`, its pending change is gone from `GET /api/pending`, other pending changes remain, and milk's quantity is unchanged

#### Scenario: Unknown event
- **WHEN** the id is unknown, already deleted, or not a door event id
- **THEN** the response is 404 `{"error": "not found"}`
