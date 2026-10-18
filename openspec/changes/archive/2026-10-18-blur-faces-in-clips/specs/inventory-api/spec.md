## MODIFIED Requirements

### Requirement: Door event listing
`GET /api/events` SHALL return `{"events": [...], "next": <id or null>}`, newest first. Each event has `id`, `opened_at`, `closed_at`, `duration_s`, `status`, `changes`, `pending_count`, `stills` and `clip`. `stills` holds 15-minute download links for its stored stills, or `[]` for events older than 7 days. `clip` is a 15-minute download link for the event's open-span clip, ending in the media fragment `#t=<start_s>,<end_s>` from its `clip_span`. It is `null` when the event has no `clip_key` or is older than 7 days. For viewer tokens it is also `null` unless the event has `clip_blurred = true`.

The range is either `days=<n>` (default 7, max 30, ending now) or `from` and `to`, ISO 8601 instants with `from` inclusive, `to` exclusive, `from` before `to` and at most 31 days apart. When `from` is given, `days` is ignored. With `limit=<n>` (1 to 50) at most `n` events are returned and `next` is the id of the last one when older events remain in the range, else null; `cursor=<id>` returns only events older than that event. Without `limit`, every event in range is returned and `next` is null.

#### Scenario: Recent event with stills
- **WHEN** a `done` door event opened 1 hour ago has 4 stored stills
- **THEN** it is listed with 4 `stills` links that download the images without any other credentials, and with its `changes`

#### Scenario: Recent event with a clip
- **WHEN** an owner or user token lists a door event opened 1 hour ago with `clip_key` set and `clip_span = [0.5, 8.5]`
- **THEN** its `clip` is a link that downloads `clip.mp4` without any other credentials and ends in `#t=0.5,8.5`

#### Scenario: Viewer gets no clip
- **WHEN** a viewer token lists the same event, which has no `clip_blurred`
- **THEN** its `clip` is `null` and its 4 `stills` links are still listed

#### Scenario: Viewer gets a blurred clip
- **WHEN** a viewer token lists a recent door event with `clip_key` set, `clip_span = [0.5, 8.5]` and `clip_blurred = true`
- **THEN** its `clip` is a link to `clip.mp4` ending in `#t=0.5,8.5`

#### Scenario: Clip still being blurred
- **WHEN** a recent door event's raw clip is waiting for the blur step (no `clip_key` yet)
- **THEN** its `clip` is `null` for every role and its `stills` are listed

#### Scenario: Event without a clip
- **WHEN** a recent door event has no `clip_key`
- **THEN** its `clip` is `null`

#### Scenario: Old event
- **WHEN** a door event opened 8 days ago and `days=30`
- **THEN** it is listed with `stills: []` and `clip: null`

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
