## ADDED Requirements

### Requirement: Every opening in the door trace
For a motion with door openings, `door.json` SHALL hold `openings`, one entry per door event in time order: `door_sk`, `opened_at`, `closed_at`, `open_span` and `picked` (still numbers), and `stored_keys`. Its top-level `door_sk`, `opened_at`, `closed_at`, `open_span`, `picked` and `stored_keys` SHALL equal the first entry's. `GET /api/debug/motions/{id}` SHALL return the motion's trace for the id of any of its door events.

#### Scenario: Two openings traced
- **WHEN** a traced motion has two openings
- **THEN** `door.json` has 2 `openings` entries whose `door_sk` values match the two door events, and the top-level `door_sk` is the first one's

#### Scenario: One opening traced
- **WHEN** a traced motion has one opening
- **THEN** `door.json` has 1 `openings` entry equal to its top-level opening fields

#### Scenario: Trace by a later opening's id
- **WHEN** the owner requests `GET /api/debug/motions/{id}` with the id of door event `DOOR#2026-08-14T13:53:16.000Z#D1#2` whose motion was traced
- **THEN** the response is 200 with the trace of motion `TRACE#2026-08-14T13:53:16.000Z#D1`
