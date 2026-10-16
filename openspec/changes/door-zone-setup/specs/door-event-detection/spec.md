# Spec Delta

## MODIFIED Requirements

### Requirement: Stills across the opening
The system SHALL request `count = clamp((end_ms − start_ms) // STILL_INTERVAL_MS, 4, 30)` JPEG stills at times `start_ms + (end_ms − start_ms) · k // (count + 1)` for `k = 1 … count`, where `STILL_INTERVAL_MS` defaults to 1000. Each still is requested with `POST /v1/devices/{device_id}/media/image/download` and `{"type": "at_timestamp", "timestamp": <ms>, "image_options": {"format": "jpeg"}}`, the redirect is followed without the `Authorization` header, and the downloaded bytes are kept in memory for the door check. For a door opening only, the system SHALL pick the stills to send on from the open span (see "Door-open check before any analysis"), crop each to the configured crop box (if any), blur any faces in it, and store only the blurred still in S3 at `accounts/<account_id>/devices/<device_id>/events/<start_ms>/still-<n>.jpg`, with `n = 1 … 4` in time order.

#### Scenario: One still per second
- **WHEN** the window is 1786715596000–1786715621000 (25 s) and `STILL_INTERVAL_MS` is unset
- **THEN** 25 stills are requested, the first at 1786715596961 and the last at 1786715620038

#### Scenario: Long window capped at 30 stills
- **WHEN** the window is 60 s long and `STILL_INTERVAL_MS` is 1000
- **THEN** exactly 30 stills are requested, evenly spaced inside the window

#### Scenario: Short window keeps 4 stills
- **WHEN** the window is 1786715596000–1786715598000 (2 s)
- **THEN** 4 stills are requested, at 1786715596400, 1786715596800, 1786715597200 and 1786715597600

#### Scenario: Invalid interval config
- **WHEN** `STILL_INTERVAL_MS` is `0`, `-500` or `fast`
- **THEN** the fetch-stills task fails with an error naming `STILL_INTERVAL_MS`, before any Ring request is made

#### Scenario: Four stills saved
- **WHEN** 25 stills are downloaded, stills 6 to 15 score as open, face detection finds no faces, and the window starts at 1786715596000
- **THEN** stills 6, 9, 13 and 16 are stored, in that order, as `still-1.jpg` … `still-4.jpg` under `accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/`

#### Scenario: Short open span
- **WHEN** only still 10 of 25 scores as open
- **THEN** stills 10 and 11 are stored as `still-1.jpg` and `still-2.jpg`, and the event goes on to analysis

#### Scenario: Download link gets no token
- **WHEN** a still is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Still not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND` for a still
- **THEN** that still is requested again, up to 3 attempts in total

#### Scenario: Too few stills
- **WHEN** fewer than 2 of the requested stills can be downloaded (including Ring's 403 for an unauthorized time range)
- **THEN** no face detection, no S3 write and no analysis happens, and the door event is saved with `status = "no_media"` and `still_keys = []`

#### Scenario: Too few stills survive face detection
- **WHEN** 4 stills are picked from the open span but face detection fails for 3 of them
- **THEN** no analysis happens, and the door event is saved with `status = "no_media"` and the one stored still's key in `still_keys`

#### Scenario: Stills deleted after 7 days
- **WHEN** a still has been stored for 7 days
- **THEN** the bucket's lifecycle rule deletes it

### Requirement: Door-open check before any analysis
The system SHALL decide for each downloaded still whether it is *open*, using rules for zones, each a box of fractions `x, y, width, height` of the downloaded still.
- **With a setup result** stored for the event's account and device (see the `door-calibration` capability), each zone has its own feature (`color`, `brightness` or `change`, measured as setup measures it, against the stored baseline for `change`), direction and threshold. A still is open when, in any zone, the feature's value is at or above the threshold (direction `above`) or at or below it (direction `below`).
- **Without a setup result**, every zone uses `color` with direction `above`: the fraction of colorful pixels, where a pixel is colorful when `max(R,G,B) − min(R,G,B) > 60` and `max(R,G,B) > 100`. The zones are `DOOR_ZONES`, else the defaults `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers), and the threshold is `DOOR_THRESHOLD`, else 0.02.

A still's *score* is the value of its best zone, the one furthest past (or closest to) its threshold. The event SHALL count as a door opening only if at least one still is open. The *open span* runs from the first open still through the first still after the last open one (or through the last open still if no still follows it). Up to 4 stills SHALL be sent on from the open span, evenly spaced and including its first and last still: positions `round(i · (n − 1) / 3)` for `i = 0 … 3` in a span of `n > 4` stills, or every still when `n ≤ 4`. The check SHALL run on the downloaded stills before any cropping, face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and one 200×100 still is grey `(128,128,128)` except a `(40,90,200)` block covering 10% of the left zone
- **THEN** the event counts as a door opening with `score` ≈ 0.10 from zone 1, and goes on to analysis

#### Scenario: Drawer opening seen only in the drawers zone
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and the only colorful pixels are a `(200,60,40)` block covering 5% of the right zone
- **THEN** the event counts as a door opening with `score` ≈ 0.05 from zone 2

#### Scenario: Setup result used for the device
- **WHEN** setup for the event's device stored zone `0.6,0.0,0.4,1.0` with `color` above 0.3, `DOOR_ZONES` is `0.0,0.0,0.4,1.0`, and only the right 40% of a still is colorful (a color value of 1.0 in the stored zone)
- **THEN** the event counts as a door opening, and the `door_event_recorded` log line has `zones_source = "setup"`

#### Scenario: Setup threshold applied
- **WHEN** setup stored `color` above 0.3 for a zone and the best still has a color value of 0.2 there
- **THEN** the event is not a door opening, although 0.2 is above `DOOR_THRESHOLD`

#### Scenario: Brightness rule applied
- **WHEN** setup stored `brightness` above 0.6 for the whole image, and the stills are plain `(200,200,200)` in one run and plain `(100,100,100)` in another
- **THEN** the first run is a door opening and the second is not

#### Scenario: Darker rule applied
- **WHEN** setup stored `brightness` below 0.5 for the whole image and a still is plain `(90,90,90)`
- **THEN** that still is open

#### Scenario: Change rule applied
- **WHEN** setup stored `change` above 0.2 for the whole image with a plain `(128,128,128)` baseline, and a still's left half is `(40,40,40)` and right half `(216,216,216)`
- **THEN** that still is open, while a plain `(130,130,130)` still is not

#### Scenario: Fallback when setup never ran
- **WHEN** no setup result is stored for the event's device and `DOOR_ZONES` is `0.6,0.0,0.4,1.0`
- **THEN** the check uses `DOOR_ZONES` and `DOOR_THRESHOLD`, and the log line has `zones_source = "default"`

#### Scenario: Setup lookup fails
- **WHEN** reading the setup result from the table raises an error
- **THEN** the check uses the defaults, logs `door_setup_unavailable` as a warning, and the run continues

#### Scenario: Door stayed closed
- **WHEN** no still reaches the threshold in any zone
- **THEN** no analysis happens, nothing is written to the inventory, no door event is saved, and a `motion_not_door` log line records `score` (the best still's value, rounded to 3 places), `zone` (1-based), `feature`, `threshold` and `zones_source`, and the run output has `outcome = "not_door"` and `score`

#### Scenario: Brightness alone does not count
- **WHEN** every still is uniform grey `(230,230,230)` (bright stainless steel in daylight) or `(30,30,30)` (dim room)
- **THEN** the score is 0 and the event is not a door opening

#### Scenario: Dark colored clothing does not count
- **WHEN** the only non-grey pixels in a zone are navy `(20,25,60)`
- **THEN** those pixels are not colorful and the event is not a door opening

#### Scenario: Threshold is inclusive
- **WHEN** a still's best zone has a colorful fraction exactly equal to the threshold
- **THEN** that still is open and the event counts as a door opening

#### Scenario: Closed door costs no face detection
- **WHEN** 25 stills are downloaded and no still reaches the threshold in any zone
- **THEN** face detection is never called and no object is written under the event's S3 prefix

#### Scenario: Box and threshold from config
- **WHEN** no setup result is stored for the device, `DOOR_ZONES` is `0.6,0.0,0.4,1.0`, and only the right 40% of a still is colorful
- **THEN** that still counts as a door opening, while with `DOOR_ZONES = 0.0,0.0,0.4,1.0` it does not

#### Scenario: Invalid zone config
- **WHEN** no setup result is stored and `DOOR_ZONES` is `0.9,0,0.5,1` (past the right edge), `0,0,1` (three numbers) or empty after splitting on `;`
- **THEN** the fetch-stills task fails with an error naming `DOOR_ZONES`, before any Ring request is made

### Requirement: Door event record
For each door opening, the system SHALL save one door event under the account with the device ID, Ring event ID, `opened_at`, `closed_at` (ISO 8601 UTC), `duration_s`, the still keys, and a `status`. `opened_at` SHALL be the request time of the first open still. `closed_at` SHALL be the request time of the first still after the last open one, or the window end when no still follows it. `duration_s` SHALL be `closed_at − opened_at` in whole seconds, rounded. An event saved with `status = "no_media"` because too few stills were downloaded SHALL take `opened_at` and `closed_at` from the window. A second run for the same Ring event SHALL NOT create a second record or a second analysis.

#### Scenario: Door event saved
- **WHEN** the window is 1786715596000–1786715621000, 25 stills are downloaded, and stills 6 to 15 are open
- **THEN** a door event exists with `opened_at = "2026-08-14T13:53:21.769Z"`, `closed_at = "2026-08-14T13:53:31.384Z"`, `duration_s = 10` and `status = "analyzing"` before analysis starts

#### Scenario: Door still open at the end of the window
- **WHEN** the last downloaded still is open
- **THEN** `closed_at` is the window end

#### Scenario: Too few stills keep the window times
- **WHEN** only 1 still could be downloaded for the window 1786715596000–1786715621000
- **THEN** the door event has `opened_at = "2026-08-14T13:53:16.000Z"`, `closed_at = "2026-08-14T13:53:41.000Z"`, `duration_s = 25` and `status = "no_media"`

#### Scenario: Same Ring event in two runs
- **WHEN** two runs resolve to the same Ring event ID and device
- **THEN** only the first run analyzes it; the second ends with `skipped_duplicate` and makes no analysis call
