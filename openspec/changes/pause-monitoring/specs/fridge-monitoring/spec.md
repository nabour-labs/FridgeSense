# Spec Delta

## Purpose

Whether FridgeSense is active or paused for a camera, so the owner can stop door openings being recorded and analyzed during cleaning, maintenance or renovation, and the routes that read and change it.

## ADDED Requirements

### Requirement: Monitoring state per camera
The system SHALL store, per Ring `account_id` and device ID, whether monitoring is paused and when it last changed. A camera with no stored state SHALL be active, `{"paused": false, "since": null}`. The state is `{"paused": <bool>, "since": "<ISO 8601 UTC>" | null}`, where `since` is when the current state began.

#### Scenario: Never paused
- **WHEN** the account's camera `ava1.ring.device.D1` has no stored monitoring state
- **THEN** its state reads `{"paused": false, "since": null}`

#### Scenario: Kept per account and device
- **WHEN** account A paused device D1, and account B has device D1 too and never paused it
- **THEN** A's D1 reads `paused: true` and B's D1 reads `paused: false`

### Requirement: Read the monitoring state
`GET /api/camera` SHALL include `monitoring` with the state of the camera it describes. It SHALL be included even when Ring is unreachable. Every signed-in role SHALL be able to read it.

#### Scenario: Paused camera
- **WHEN** a viewer calls `GET /api/camera` after the owner paused the camera at `2026-10-18T14:05:00.000Z`
- **THEN** the response is 200 with `monitoring: {"paused": true, "since": "2026-10-18T14:05:00.000Z"}`

#### Scenario: Ring unreachable
- **WHEN** the Ring device call answers 500 and the camera is paused
- **THEN** the response is 200 with `ring: "unavailable"` and the same `monitoring` object

### Requirement: Pause and resume
`PUT /api/camera/monitoring` with `{"paused": true}` or `{"paused": false}` SHALL store that state for the account's first discovered camera and return 200 `{"paused": <bool>, "since": "<now, ISO 8601 UTC>"}`. Sending the current state again SHALL return 200 and keep its `since` unchanged.

#### Scenario: Pause
- **WHEN** the owner sends `{"paused": true}` at `2026-10-18T14:05:00.000Z` and the camera is active
- **THEN** the response is 200 `{"paused": true, "since": "2026-10-18T14:05:00.000Z"}` and the next `GET /api/camera` shows the same `monitoring`

#### Scenario: Resume
- **WHEN** the camera is paused and the owner sends `{"paused": false}` at `2026-10-18T16:30:00.000Z`
- **THEN** the response is 200 `{"paused": false, "since": "2026-10-18T16:30:00.000Z"}`

#### Scenario: Pause twice
- **WHEN** the camera was paused at `2026-10-18T14:05:00.000Z` and `{"paused": true}` is sent again at `2026-10-18T15:00:00.000Z`
- **THEN** the response is 200 with `since: "2026-10-18T14:05:00.000Z"`

#### Scenario: Bad body
- **WHEN** the body is `{"paused": "yes"}`, `{}` or not JSON
- **THEN** the response is 400 `{"error": "paused must be true or false"}` and the stored state is unchanged

### Requirement: Pausing is a write
`PUT /api/camera/monitoring` SHALL follow the existing write rules: it needs a valid token, a viewer token SHALL get 403 `{"error": "read-only"}`, and an account with no discovered camera SHALL get 409 `{"error": "no camera found"}`.

#### Scenario: Viewer cannot pause
- **WHEN** a viewer token sends `{"paused": true}`
- **THEN** the response is 403 `{"error": "read-only"}` and the camera stays active

#### Scenario: User role can pause
- **WHEN** a user-role token sends `{"paused": true}`
- **THEN** the response is 200 with `paused: true`

#### Scenario: No token
- **WHEN** `PUT /api/camera/monitoring` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

#### Scenario: No camera
- **WHEN** the account has no discovered device
- **THEN** the response is 409 `{"error": "no camera found"}`
