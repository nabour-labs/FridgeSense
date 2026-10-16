# door-event-detection Specification

## Purpose
Turns a Ring motion event from the fridge camera into a door event: when the door opened and closed, stills of the opening, and whether it really was a door opening worth analyzing.

## Requirements

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
The system SHALL request 4 JPEG stills at evenly spaced times inside the window (at 1/5, 2/5, 3/5 and 4/5 of it) with `POST /v1/devices/{device_id}/media/image/download` and `{"type": "at_timestamp", "timestamp": <ms>, "image_options": {"format": "jpeg"}}`, follow the redirect without the `Authorization` header, and keep the downloaded bytes in memory for the door check. For a door opening only, it SHALL crop each still to the configured crop box (if any), blur any faces in it, and store only the blurred still in S3 at `accounts/<account_id>/devices/<device_id>/events/<start_ms>/still-<n>.jpg`.

#### Scenario: Four stills saved
- **WHEN** the window is 1786715596000–1786715621000, Ring answers each request with 303 and a `Location`, the download returns JPEG bytes that pass the door check, and face detection finds no faces
- **THEN** requests are made for timestamps 1786715601000, 1786715606000, 1786715611000 and 1786715616000, and four objects `still-1.jpg` … `still-4.jpg` exist under `accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/`

#### Scenario: Download link gets no token
- **WHEN** a still is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Still not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND` for a still
- **THEN** that still is requested again, up to 3 attempts in total

#### Scenario: Too few stills
- **WHEN** fewer than 2 of the 4 stills can be downloaded (including Ring's 403 for an unauthorized time range)
- **THEN** no face detection, no S3 write and no analysis happens, and the door event is saved with `status = "no_media"` and `still_keys = []`

#### Scenario: Too few stills survive face detection
- **WHEN** 4 stills that pass the door check are downloaded but face detection fails for 3 of them
- **THEN** no analysis happens, and the door event is saved with `status = "no_media"` and the one stored still's key in `still_keys`

#### Scenario: Stills deleted after 7 days
- **WHEN** a still has been stored for 7 days
- **THEN** the bucket's lifecycle rule deletes it

### Requirement: Door-open check before any analysis
The system SHALL compute, for each configured zone (fractions `x, y, width, height` of the downloaded still) in each downloaded still, the fraction of colorful pixels, where a pixel is colorful when `max(R,G,B) − min(R,G,B) > 60` and `max(R,G,B) > 100`. The event SHALL count as a door opening only if the highest fraction over all zones and stills reaches the configured threshold (default 0.02). Zones SHALL default to `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers). The check SHALL run on the downloaded stills before any cropping, face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and one 200×100 still is grey `(128,128,128)` except a `(40,90,200)` block covering 10% of the left zone
- **THEN** the event counts as a door opening with `score` ≈ 0.10 from zone 1, and goes on to analysis

#### Scenario: Drawer opening seen only in the drawers zone
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and the only colorful pixels are a `(200,60,40)` block covering 5% of the right zone
- **THEN** the event counts as a door opening with `score` ≈ 0.05 from zone 2

#### Scenario: Door stayed closed
- **WHEN** every zone of every still has a colorful fraction below the threshold
- **THEN** no analysis happens, nothing is written to the inventory, no door event is saved, and a `motion_not_door` log line records `score` (the highest fraction, rounded to 3 places), `zone` (1-based) and `threshold`, and the run output has `outcome = "not_door"` and `score`

#### Scenario: Brightness alone does not count
- **WHEN** every still is uniform grey `(230,230,230)` (bright stainless steel in daylight) or `(30,30,30)` (dim room)
- **THEN** the score is 0 and the event is not a door opening

#### Scenario: Dark colored clothing does not count
- **WHEN** the only non-grey pixels in a zone are navy `(20,25,60)`
- **THEN** those pixels are not colorful and the event is not a door opening

#### Scenario: Threshold is inclusive
- **WHEN** a still's best zone has a colorful fraction exactly equal to the threshold
- **THEN** the event counts as a door opening

#### Scenario: Closed door costs no face detection
- **WHEN** 4 stills are downloaded and every zone of every still is below the threshold
- **THEN** face detection is never called and no object is written under the event's S3 prefix

#### Scenario: Box and threshold from config
- **WHEN** `DOOR_ZONES` is `0.6,0.0,0.4,1.0` and only the right 40% of a still is colorful
- **THEN** that still counts as a door opening, while with `DOOR_ZONES = 0.0,0.0,0.4,1.0` it does not

#### Scenario: Invalid zone config
- **WHEN** `DOOR_ZONES` is `0.9,0,0.5,1` (past the right edge), `0,0,1` (three numbers) or empty after splitting on `;`
- **THEN** the fetch-stills task fails with an error naming `DOOR_ZONES`, before any Ring request is made

### Requirement: Door event record
For each door opening, the system SHALL save one door event under the account with the device ID, Ring event ID, `opened_at` and `closed_at` (ISO 8601 UTC from the window), `duration_s`, the still keys, and a `status`. A second run for the same Ring event SHALL NOT create a second record or a second analysis.

#### Scenario: Door event saved
- **WHEN** a door opening with window 1786715596000–1786715621000 is processed
- **THEN** a door event exists with `opened_at = "2026-08-14T13:53:16.000Z"`, `closed_at = "2026-08-14T13:53:41.000Z"`, `duration_s = 25` and `status = "analyzing"` before analysis starts

#### Scenario: Same Ring event in two runs
- **WHEN** two runs resolve to the same Ring event ID and device
- **THEN** only the first run analyzes it; the second ends with `skipped_duplicate` and makes no analysis call

### Requirement: Faces blurred before storage
Before a still is stored, the system SHALL send it (after cropping, if a crop box is configured) to face detection and SHALL blur every face reported, whatever its confidence. Each face box (fractions of the image sent to detection) SHALL be enlarged by 30% about its centre, clipped to the image, and made unrecognizable. With no crop box and no faces, the still SHALL be stored byte for byte as downloaded.

#### Scenario: One face found
- **WHEN** a 320×180 still with a black-and-white checkerboard of 4 px squares is downloaded, and face detection reports one face with `BoundingBox = {"Left": 0.40, "Top": 0.20, "Width": 0.20, "Height": 0.30}` and `Confidence = 99.1`
- **THEN** the stored still's luminance standard deviation inside the enlarged box `(0.37, 0.155, 0.26, 0.39)` is below 10 (of 255), and outside that box its mean absolute difference from the downloaded still is at most 3

#### Scenario: Two faces found
- **WHEN** face detection reports two faces at `(0.05, 0.10, 0.15, 0.25)` and `(0.70, 0.30, 0.15, 0.25)` on the checkerboard still
- **THEN** both enlarged boxes have luminance standard deviation below 10 in the stored still

#### Scenario: Low-confidence face still blurred
- **WHEN** face detection reports one face at `(0.40, 0.20, 0.20, 0.30)` with `Confidence = 50.2`
- **THEN** that face's enlarged box is blurred exactly as for a high-confidence face

#### Scenario: Face at the image edge
- **WHEN** face detection reports a face at `(0.90, -0.05, 0.15, 0.25)`, which runs past the right and top edges
- **THEN** the enlarged box is clipped to the image, the visible part of it is blurred, and no error occurs

#### Scenario: No face found
- **WHEN** no crop box is configured and face detection reports no faces for a still
- **THEN** the stored object's bytes are identical to the downloaded bytes

#### Scenario: Detection sees the downloaded bytes, S3 sees only the result
- **WHEN** a still is downloaded and face detection reports one face
- **THEN** the detection request carries the JPEG bytes inline (not an S3 reference): the downloaded bytes with no crop box, or the cropped JPEG with one. The only object written for that still is the blurred JPEG with `ContentType = "image/jpeg"`

### Requirement: Fail closed when face detection fails
If face detection fails for a still (any service error, throttling, timeout, or an image it rejects), the system SHALL drop that still: nothing is stored for it, it does not count toward the stills downloaded, and a `face_detect_failed` warning is logged with the still number and the error code. An unblurred still SHALL never be stored.

#### Scenario: Detection fails for one still
- **WHEN** face detection answers `ThrottlingException` for still 2 and reports no faces for stills 1, 3 and 4
- **THEN** only `still-1.jpg`, `still-3.jpg` and `still-4.jpg` are stored, the door event's `still_keys` lists those three, and a `face_detect_failed` log line has `still = 2` and `error = "ThrottlingException"`

#### Scenario: Detection fails for every still
- **WHEN** face detection answers `InternalServerError` for all 4 stills of a door opening
- **THEN** no object is stored under the event's prefix, no analysis happens, and the door event is saved with `status = "no_media"` and `still_keys = []`

#### Scenario: Image rejected by detection
- **WHEN** face detection answers `InvalidImageFormatException` or `ImageTooLargeException` for a still
- **THEN** that still is dropped the same way as for any other detection error

### Requirement: Face detection cost logged per still
For every successful face-detection call, the system SHALL log a `face_detect_cost` line with `account_id`, `device_id`, `still` (1–4), `faces` (count found) and `usd`. The price per image SHALL default to 0.001 USD and SHALL be overridable through configuration.

#### Scenario: Default price
- **WHEN** face detection succeeds for still 3 of device `ava1.ring.device.D1` and finds 1 face, with no price configured
- **THEN** a `face_detect_cost` line has `still = 3`, `faces = 1` and `usd = 0.001`

#### Scenario: Configured price
- **WHEN** the configured price per image is `0.0008` and detection succeeds with no faces
- **THEN** the `face_detect_cost` line has `faces = 0` and `usd = 0.0008`

#### Scenario: Failed call is not costed
- **WHEN** face detection fails for a still
- **THEN** no `face_detect_cost` line is logged for that still

### Requirement: No door event left analyzing
Once a door event has been recorded with `status = "analyzing"`, the workflow run SHALL end with that event in a final status. If the analysis or the save of its changes fails for any reason, the event's `status` SHALL become `"analysis_failed"`, the failure SHALL be logged as `analysis_failed` with the error name, and the inventory SHALL be unchanged by that run.

#### Scenario: Save fails
- **WHEN** the save step of a run fails with any error (for example a DynamoDB error or a task timeout)
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

#### Scenario: Analysis fails
- **WHEN** the analyze step fails with any error after its retries
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

### Requirement: Only blurred stills are analyzed
The item analysis SHALL use only the stored (blurred and, if configured, cropped) stills. No unblurred still SHALL be sent to the analysis model or stored. The door check reads the downloaded, uncropped stills in memory only.

#### Scenario: Analysis receives blurred bytes
- **WHEN** a door opening's still 1 had a face blurred and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes

#### Scenario: Door check runs on downloaded stills
- **WHEN** a downloaded still passes the door check and contains a face
- **THEN** the event counts as a door opening, face detection is called only after the door check, and only the blurred still is stored

### Requirement: Stills cropped to the visible area
When `STILL_CROP` is set (fractions `x, y, width, height` of the downloaded still), the system SHALL crop each still of a door opening to that box and re-encode it as JPEG before face detection, so the stored still and the analysis image are the crop. When `STILL_CROP` is unset or empty, stills SHALL NOT be cropped. Stills of events that fail the door check SHALL never be cropped or stored.

#### Scenario: Crop to the visible strip
- **WHEN** `STILL_CROP` is `0.30,0.0,0.34,1.0` and a door opening's still is 2560×1440
- **THEN** the image sent to face detection and the stored `still-<n>.jpg` are 870×1440 (±1 px per side), and their pixels match the downloaded still's region starting at x = 768

#### Scenario: Analysis sees the cropped still
- **WHEN** `STILL_CROP` is set and the event goes on to analysis
- **THEN** each image in the analysis request has the cropped dimensions and equals the stored object

#### Scenario: No crop configured
- **WHEN** `STILL_CROP` is not set
- **THEN** the stored still has the downloaded dimensions, and with no faces its bytes are identical to the downloaded bytes

#### Scenario: Door check ignores the crop
- **WHEN** `STILL_CROP` is `0.0,0.0,0.5,1.0` and the only colorful pixels are in a zone at `0.6,0.0,0.4,1.0`
- **THEN** the event still counts as a door opening, because the door check uses the uncropped still

#### Scenario: Invalid crop config
- **WHEN** `STILL_CROP` is `0.8,0,0.5,1` (past the right edge) or `0,0,1` (three numbers)
- **THEN** the fetch-stills task fails with an error naming `STILL_CROP`, before any Ring request is made
