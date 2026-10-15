# Spec Delta

## Purpose

Turns a Ring motion event from the fridge camera into a door event: when the door opened and closed, stills of the opening, and whether it really was a door opening worth analyzing.

## ADDED Requirements

### Requirement: One workflow run per motion event
For each motion event handed over by the webhook, the system SHALL start one door-event workflow run with input `{"account_id", "device_id", "timestamp_ms", "request_id"}`, named from the device ID and `timestamp_ms` so the same event can never start two runs.

#### Scenario: Motion event starts a run
- **WHEN** the motion handler receives account `ava1.ring.account.A1`, device `ava1.ring.device.D1`, `timestamp_ms = 1786715596787`, request `R1`
- **THEN** one workflow run starts with exactly that input, and its name contains `1786715596787`

#### Scenario: Same event handed over twice
- **WHEN** a run for the same device and `timestamp_ms` already exists
- **THEN** no second run starts and the hand-over still succeeds

### Requirement: Event window from Ring's history
The system SHALL find the event window by calling `GET /v1/history/devices/{device_id}/events?event_types=motion` and picking the event whose `attributes.start` (epoch ms, number or numeric string) is within 10 s of `timestamp_ms`. The window is ready only when that event has an `attributes.end`.

#### Scenario: Recording finished
- **WHEN** history returns an event with `start = 1786715596000` and `end = 1786715621000` and the motion `timestamp_ms` is 1786715596787
- **THEN** the window is `start_ms = 1786715596000`, `end_ms = 1786715621000`, and the Ring event ID is kept

#### Scenario: Timestamps as strings
- **WHEN** history returns `"start": "1786715596000"` and `"end": "1786715621000"`
- **THEN** the window is the same as when they are numbers

#### Scenario: Recording not finished yet
- **WHEN** the matching event has no `end`, or no event within 10 s is listed yet
- **THEN** the window is reported as pending and the workflow waits 20 s and asks again

#### Scenario: Recording never finishes
- **WHEN** the window is still pending after 6 checks
- **THEN** the workflow uses `start_ms = timestamp_ms`, `end_ms = timestamp_ms + 30000` and continues

### Requirement: Stills across the opening
The system SHALL request 4 JPEG stills at evenly spaced times inside the window (at 1/5, 2/5, 3/5 and 4/5 of it) with `POST /v1/devices/{device_id}/media/image/download` and `{"type": "at_timestamp", "timestamp": <ms>, "image_options": {"format": "jpeg"}}`, follow the redirect without the `Authorization` header, and store each still in S3 at `accounts/<account_id>/devices/<device_id>/events/<start_ms>/still-<n>.jpg`.

#### Scenario: Four stills saved
- **WHEN** the window is 1786715596000–1786715621000 and Ring answers each request with 303 and a `Location`, and the download returns JPEG bytes
- **THEN** requests are made for timestamps 1786715601000, 1786715606000, 1786715611000 and 1786715616000, and four objects `still-1.jpg` … `still-4.jpg` exist under `accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/`

#### Scenario: Download link gets no token
- **WHEN** a still is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Still not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND` for a still
- **THEN** that still is requested again, up to 3 attempts in total

#### Scenario: Too few stills
- **WHEN** fewer than 2 of the 4 stills can be downloaded (including Ring's 403 for an unauthorized time range)
- **THEN** no analysis happens, and the door event is saved with `status = "no_media"`

#### Scenario: Stills deleted after 7 days
- **WHEN** a still has been stored for 7 days
- **THEN** the bucket's lifecycle rule deletes it

### Requirement: Door-open check before any analysis
The system SHALL compute the mean brightness (0–1) of a configured box (fractions `x, y, width, height` of the image) in each still, and SHALL treat the event as a door opening only if the brightest still reaches the configured threshold. Only door openings go on to analysis.

#### Scenario: Fridge light visible
- **WHEN** one still's box has mean brightness 0.8 and the threshold is 0.5
- **THEN** the event counts as a door opening and goes on to analysis

#### Scenario: Door stayed closed
- **WHEN** every still's box is below the threshold
- **THEN** no analysis happens, nothing is written to the inventory, no door event is saved, and a `motion_not_door` log line records the brightest value

#### Scenario: Box and threshold from config
- **WHEN** the box is configured as `0.6,0.0,0.4,1.0` and only the right 40% of a still is bright
- **THEN** that still counts as bright, while with the box `0.0,0.0,0.4,1.0` it does not

### Requirement: Door event record
For each door opening, the system SHALL save one door event under the account with the device ID, Ring event ID, `opened_at` and `closed_at` (ISO 8601 UTC from the window), `duration_s`, the still keys, and a `status`. A second run for the same Ring event SHALL NOT create a second record or a second analysis.

#### Scenario: Door event saved
- **WHEN** a door opening with window 1786715596000–1786715621000 is processed
- **THEN** a door event exists with `opened_at = "2026-08-14T13:53:16.000Z"`, `closed_at = "2026-08-14T13:53:41.000Z"`, `duration_s = 25` and `status = "analyzing"` before analysis starts

#### Scenario: Same Ring event in two runs
- **WHEN** two runs resolve to the same Ring event ID and device
- **THEN** only the first run analyzes it; the second ends with `skipped_duplicate` and makes no analysis call
