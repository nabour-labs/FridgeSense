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
- **With a setup result** stored for the event's account and device (see the `door-calibration` capability), each zone has its own feature (`blue`, `color`, `brightness` or `change`, measured as setup measures it, against the stored baseline for `change`), direction and threshold. A still is open when, in any zone, the feature's value is at or above the threshold (direction `above`) or at or below it (direction `below`).
- **Without a setup result**, every zone uses `blue` with direction `above`: the fraction of pixels that are both colorful (`max(R,G,B) − min(R,G,B) > 60` and `max(R,G,B) > 100`) and blue-lit (`B − max(R,G) > 20`), as the fridge's LED-lit interior is. Warm colors such as food held in front of the closed doors do not count. The zones are `DOOR_ZONES`, else the defaults `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers), and the threshold is `DOOR_THRESHOLD`, else 0.01.

A still's *score* is the value of its best zone, the one furthest past (or closest to) its threshold. The event SHALL count as a door opening only if at least one still is open. The *open span* runs from the first open still through the first still after the last open one (or through the last open still if no still follows it). Up to 4 stills SHALL be sent on from the open span, evenly spaced and including its first and last still: positions `round(i · (n − 1) / 3)` for `i = 0 … 3` in a span of `n > 4` stills, or every still when `n ≤ 4`. The check SHALL run on the downloaded stills before any cropping, face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and one 200×100 still is grey `(128,128,128)` except a `(40,90,200)` block covering 10% of the left zone
- **THEN** the event counts as a door opening with `score` ≈ 0.10 from zone 1, and goes on to analysis

#### Scenario: Drawer opening seen only in the drawers zone
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and the only blue-lit pixels are a `(40,90,200)` block covering 5% of the right zone
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
- **WHEN** a still's best zone has a feature value exactly equal to the threshold
- **THEN** that still is open and the event counts as a door opening

#### Scenario: Closed door costs no face detection
- **WHEN** 25 stills are downloaded and no still reaches the threshold in any zone
- **THEN** face detection is never called and no object is written under the event's S3 prefix

#### Scenario: Box and threshold from config
- **WHEN** no setup result is stored for the device, `DOOR_ZONES` is `0.6,0.0,0.4,1.0`, and only the right 40% of a still is blue-lit `(40,90,200)`
- **THEN** that still counts as a door opening, while with `DOOR_ZONES = 0.0,0.0,0.4,1.0` it does not

#### Scenario: Invalid zone config
- **WHEN** no setup result is stored and `DOOR_ZONES` is `0.9,0,0.5,1` (past the right edge), `0,0,1` (three numbers) or empty after splitting on `;`
- **THEN** the fetch-stills task fails with an error naming `DOOR_ZONES`, before any Ring request is made

#### Scenario: Food in front of closed doors
- **WHEN** no setup result is stored, zones are `0.0,0.0,1.0,1.0`, and every still is grey `(128,128,128)` except a yellow `(220,170,40)` plate covering 10% of the zone, or a red `(200,40,40)` packet covering 10%
- **THEN** the score is 0, no still is open, and the event is not a door opening

#### Scenario: Faint fridge light counts at the default threshold
- **WHEN** no setup result is stored, `DOOR_THRESHOLD` is unset, zones are `0.0,0.0,1.0,1.0`, and a still is grey except a `(40,90,200)` block covering 1.5% of the zone
- **THEN** that still is open (1.5% is at least the 0.01 default), and the event counts as a door opening

#### Scenario: Stored color setup still works
- **WHEN** setup for the device stored a zone with `color` above 0.05 and a still has a `(220,170,40)` block covering 10% of that zone
- **THEN** that still is open, because the stored rule's feature is `color`

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
If face detection fails for a still (any service error, throttling, timeout, or an image it rejects), the system SHALL drop that still: nothing is stored for it, it does not count toward the stills downloaded, and a `face_detect_failed` warning is logged with the still number and the error code. An unblurred still SHALL never be stored as an event still or sent to analysis. The only unblurred copies are the owner-only debug trace's `debug/raw-<n>.jpg`. They are written only while `DEBUG_TRACES` is on and expire with the bucket's 7-day lifecycle.

#### Scenario: Detection fails for one still
- **WHEN** face detection answers `ThrottlingException` for still 2 and reports no faces for stills 1, 3 and 4
- **THEN** only `still-1.jpg`, `still-3.jpg` and `still-4.jpg` are stored, the door event's `still_keys` lists those three, and a `face_detect_failed` log line has `still = 2` and `error = "ThrottlingException"`

#### Scenario: Detection fails for every still
- **WHEN** face detection answers `InternalServerError` for all 4 stills of a door opening
- **THEN** no `still-<n>.jpg` object is stored under the event's prefix, no analysis happens, and the door event is saved with `status = "no_media"` and `still_keys = []`

#### Scenario: Image rejected by detection
- **WHEN** face detection answers `InvalidImageFormatException` or `ImageTooLargeException` for a still
- **THEN** that still is dropped the same way as for any other detection error

#### Scenario: Debug copy is not an event still
- **WHEN** `DEBUG_TRACES` is on and face detection fails for still 2
- **THEN** `debug/raw-2.jpg` may exist, but no `still-<n>.jpg` holds still 2's bytes and `still_keys` does not list it

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
Once a door event has been recorded with `status = "analyzing"`, the workflow run SHALL end with that event in a final status. If the analysis or the save of its changes fails for any reason, the event's `status` SHALL become `"analysis_failed"`, the failure SHALL be logged as `analysis_failed` with the error name, and the inventory SHALL be unchanged by that run. After marking the event failed, the run SHALL end as a failed execution so the failed-run alarm counts it.

#### Scenario: Save fails
- **WHEN** the save step of a run fails with any error (for example a DynamoDB error or a task timeout)
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

#### Scenario: Analysis fails
- **WHEN** the analyze step fails with any error after its retries
- **THEN** the run goes to the mark-failed step and the door event's `status` is `"analysis_failed"`

#### Scenario: Failed run ends as a failed execution
- **WHEN** the mark-failed step finishes
- **THEN** the run moves to a `Fail` state named `AnalysisFailed` with error `AnalysisFailed`, so the execution's status is `FAILED`

### Requirement: Only blurred stills are analyzed
The item analysis SHALL use only the stored (blurred and, if configured, cropped) stills. No unblurred still SHALL be sent to the analysis model or stored as an event still. The door check reads the downloaded, uncropped stills in memory. Unblurred copies are kept only as the owner-only debug trace's raw stills.

#### Scenario: Analysis receives blurred bytes
- **WHEN** a door opening's still 1 had a face blurred and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes or `debug/raw-<n>.jpg`

#### Scenario: Door check runs on downloaded stills
- **WHEN** a downloaded still passes the door check and contains a face
- **THEN** the event counts as a door opening, face detection is called only after the door check, and the only stored event still is the blurred one

#### Scenario: No debug stills when tracing is off
- **WHEN** `DEBUG_TRACES=false` and a downloaded still contains a face
- **THEN** no unblurred copy of it is stored anywhere

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

### Requirement: Door check on the event clip
The fetch-stills step SHALL first request the event clip once with `POST /v1/devices/{device_id}/media/video/download` and `{"timestamp": <start_ms>, "duration": <end_ms − start_ms>}`. It SHALL follow the 303 `Location` without the `Authorization` header. It SHALL then run the door check on the frame shown at every `DOOR_FRAME_INTERVAL_MS` offset from 0 up to, but not including, the clip's duration. Each frame's time is `start_ms` plus its offset.

#### Scenario: One clip request per event
- **WHEN** the window is 1786715596000–1786715616000 and Ring answers the clip request with 303 and a `Location` to a 20.0 s MP4
- **THEN** exactly one clip request is made, with body `{"timestamp": 1786715596000, "duration": 20000}`

#### Scenario: Frame every 500 ms
- **WHEN** `DOOR_FRAME_INTERVAL_MS` is unset and the clip lasts 20.0 s
- **THEN** the door check runs on 40 frames, at offsets 0, 500, …, 19500 ms

#### Scenario: Frame shown at an offset
- **WHEN** the clip has frames starting at 0, 400 and 800 ms and the offset is 500 ms
- **THEN** the frame that starts at 400 ms is checked

#### Scenario: Clip link gets no token
- **WHEN** the clip is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Clip not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND`, either to the clip request or to the `Location` download after a 303, and then a later attempt returns the MP4
- **THEN** the whole request (POST, then link) is repeated and the door check runs on the clip's frames, up to 3 attempts in total

#### Scenario: Not a door opening
- **WHEN** no frame passes the door check
- **THEN** the outcome is `not_door`, no still is requested, and there is no face detection, S3 write or analysis

#### Scenario: Short opening between stills
- **WHEN** a 121.9 s clip shows the door open only from 63.7 s to 66.7 s
- **THEN** the outcome is `door_open`, although 30 stills spread across the window would all fall outside the opening

### Requirement: Open and close times from clip frames
For a door opening found in the clip, `opened_at` SHALL be the time of the first open frame. `closed_at` SHALL be the time of the first closed frame after the last open frame, or `end_ms` if no closed frame follows. `duration_s` SHALL be their difference, rounded to whole seconds.

#### Scenario: Open and close times
- **WHEN** the window starts at 1786715596000 and the frames at offsets 4000–12000 ms are open while the frame at 12500 ms is closed
- **THEN** the door event has `opened_at = "2026-08-14T13:53:20.000Z"`, `closed_at = "2026-08-14T13:53:28.500Z"` and `duration_s = 8`

#### Scenario: Still open at the end of the clip
- **WHEN** the window is 1786715596000–1786715616000 and every frame from offset 15000 ms to the last one is open
- **THEN** `closed_at` is `"2026-08-14T13:53:36.000Z"` (the window end)

### Requirement: Stills for an opening found in the clip
For a door opening found in the clip, the system SHALL pick up to 4 times from the open span. The span runs from the first open frame through the first closed frame after the last open one. The picks are evenly spaced and always include the span's first and last frame. For each picked time, the system SHALL request a Ring still at that time with the existing still request and retries. If a still can't be downloaded, its clip frame SHALL be used instead, encoded as JPEG. These stills are then cropped, face-blurred, stored as `still-<n>.jpg` and analyzed exactly as stills are today.

#### Scenario: Four stills from the open span
- **WHEN** the frame interval is 500 ms, the frames at offsets 4000–12000 ms are open and the frame at 12500 ms is closed
- **THEN** stills are requested at `start_ms` + 4000, 7000, 9500 and 12500 ms, and `still-1.jpg` … `still-4.jpg` are stored after face blurring

#### Scenario: Short open span
- **WHEN** only the frame at offset 6000 ms is open and the frame at 6500 ms is closed
- **THEN** exactly two stills are requested, at `start_ms` + 6000 and 6500 ms

#### Scenario: Still missing, frame used
- **WHEN** Ring answers 403 for the still at `start_ms` + 7000 ms
- **THEN** the clip frame at offset 7000 ms is face-blurred and stored as that still, and analysis still gets 4 stills

### Requirement: Fall back to still sampling without the clip
If the clip can't be used, the system SHALL log `clip_unavailable` with the device ID and a `reason`, then run the door check on sampled stills as it does today. The reasons are: `status_<code>` (any other HTTP status from the request or the link, or 425/416 after 3 attempts), `download_failed` (Ring, OAuth or network error), `too_large` (more than 300 MB), `decode_failed` (not a readable video) and `no_frames` (no frame at offset 0). A clip problem SHALL NOT make the step fail or drop a door opening.

#### Scenario: Ring refuses the clip
- **WHEN** Ring answers the clip request with 403
- **THEN** `clip_unavailable` is logged with `reason = "status_403"`, and the door check runs on stills as before

#### Scenario: Clip never ready
- **WHEN** Ring answers 303 to all 3 clip requests and each `Location` download answers 416 `MEDIA_NOT_FOUND`
- **THEN** `clip_unavailable` is logged with `reason = "status_416"`, and the door check runs on stills

#### Scenario: Clip request never ready
- **WHEN** Ring answers 425 to all 3 clip requests
- **THEN** `clip_unavailable` is logged with `reason = "status_425"`, and the door check runs on stills

#### Scenario: Unreadable clip
- **WHEN** the `Location` download returns bytes that are not a video
- **THEN** `clip_unavailable` is logged with `reason = "decode_failed"`, and the door check runs on stills

#### Scenario: Clip too large
- **WHEN** the clip download announces or streams more than 300 MB
- **THEN** the download stops, `clip_unavailable` is logged with `reason = "too_large"`, and the door check runs on stills

#### Scenario: Network error
- **WHEN** the clip request raises a network error
- **THEN** `clip_unavailable` is logged with `reason = "download_failed"`, and the door check runs on stills

### Requirement: Frame interval setting
`DOOR_FRAME_INTERVAL_MS` SHALL set the milliseconds between checked frames: a whole number above 0, default 500. An invalid value SHALL fail the fetch-stills step with an error naming `DOOR_FRAME_INTERVAL_MS`, before any Ring request.

#### Scenario: Interval from config
- **WHEN** `DOOR_FRAME_INTERVAL_MS = 1000` and the clip lasts 20.0 s
- **THEN** 20 frames are checked, at offsets 0, 1000, …, 19000 ms

#### Scenario: Invalid interval
- **WHEN** `DOOR_FRAME_INTERVAL_MS` is `0`, `-5` or `abc`
- **THEN** the step fails with an error naming `DOOR_FRAME_INTERVAL_MS`, and no Ring request is made

### Requirement: Clips never stored
The clip SHALL only be held in memory or in a temporary file in Lambda `/tmp`. The temporary file SHALL be deleted when the step ends, whether it succeeds or fails. No clip, and no frame other than the stored stills and the debug-trace frames, SHALL be written to S3.

#### Scenario: Door opening processed
- **WHEN** a door opening is processed from a clip with debug traces off
- **THEN** the only S3 objects written are `still-<n>.jpg`, and no `.mp4` object exists in the bucket

#### Scenario: Temporary file removed on error
- **WHEN** decoding fails partway through the clip
- **THEN** the temporary clip file no longer exists after the step

### Requirement: Window and stills steps retried and caught
The find-window and fetch-stills steps SHALL retry a task failure (`States.TaskFailed`) twice, 10 s apart then 20 s. Any error left after the retries SHALL send the run to the mark-failed step with the error at `$.error`. The mark-failed step SHALL set the door event's `status` to `"analysis_failed"` only when the run already has a `door_sk`; without one it SHALL only log `analysis_failed` with the error name and account ID.

#### Scenario: Window step retries and is caught
- **WHEN** the state machine is synthesized
- **THEN** `FindWindow` has a retry on `["States.TaskFailed"]` with `IntervalSeconds = 10`, `MaxAttempts = 2`, `BackoffRate = 2`, and a catch on `["States.ALL"]` with `ResultPath = "$.error"` to `MarkFailed`

#### Scenario: Stills step retries and is caught
- **WHEN** the state machine is synthesized
- **THEN** `FetchStills` has the same retry and the same catch to `MarkFailed`

#### Scenario: Failure before the door event exists
- **WHEN** the mark-failed step runs with `{"account_id": "acc-1", "error": {"Error": "RingTimeout"}}` and no `door_sk`
- **THEN** it logs `analysis_failed` with `reason = "RingTimeout"`, writes no door event, and returns the state with `outcome = "analysis_failed"`
