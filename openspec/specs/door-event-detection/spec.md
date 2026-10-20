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
- **Without a setup result**, every zone uses `blue` with direction `above`: the fraction of pixels that are both strongly colorful (`max(R,G,B) − min(R,G,B) > 100` and `max(R,G,B) > 120`) and strongly blue-lit (`B − max(R,G) > 60`), as the fridge's LED-lit interior is. Warm colors such as food held in front of the closed doors do not count, and neither does the cool tint daylight gives the steel doors. The zones are `DOOR_ZONES`, else the defaults `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers), and the threshold is `DOOR_THRESHOLD`, else 0.01.

A still's *score* is the value of its best zone, the one furthest past (or closest to) its threshold. The event SHALL count as a door opening only if at least one still is open. A run of closed stills SHALL end an opening when the time from its first closed still to the next open still is 10 s or more; a shorter closed run stays inside the opening. Each opening's *open span* runs from its first open still through the first still after its last open one (or through its last open still if no still follows it). Up to 4 stills SHALL be sent on from each open span, evenly spaced and including its first and last still: positions `round(i · (n − 1) / 3)` for `i = 0 … 3` in a span of `n > 4` stills, or every still when `n ≤ 4`. The check SHALL run on the downloaded stills before any cropping, face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and one 200×100 still is grey `(128,128,128)` except a `(40,90,200)` block covering 10% of the left zone
- **THEN** the event counts as a door opening with `score` ≈ 0.10 from zone 1, and goes on to analysis

#### Scenario: Drawer opening seen only in the drawers zone
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and the only blue-lit pixels are a `(40,90,200)` block covering 5% of the right zone
- **THEN** the event counts as a door opening with `score` ≈ 0.05 from zone 2

#### Scenario: Setup result used for the device
- **WHEN** setup for the event's device stored zone `0.6,0.0,0.4,1.0` with `color` above 0.3, `DOOR_ZONES` is `0.0,0.0,0.4,1.0`, and only the right 40% of a still is colorful (a color value of 1.0 in the stored zone)
- **THEN** the event counts as a door opening, and the `door_event_recorded` log line has `zones_source = "setup"`

#### Scenario: Short closed run stays inside the opening
- **WHEN** 25 stills one second apart are downloaded, stills 6–10 and 15–20 are open, and stills 11–14 are closed (4 s from still 11 to still 15)
- **THEN** there is one opening whose open span is stills 6–21

#### Scenario: Long closed run splits the opening
- **WHEN** 30 stills one second apart are downloaded, stills 3–6 and 20–24 are open, and stills 7–19 are closed (13 s from still 7 to still 20)
- **THEN** there are two openings, with open spans stills 3–7 and stills 20–25

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

#### Scenario: Cool daylight on closed doors
- **WHEN** no setup result is stored, zones are `0.0,0.0,1.0,1.0`, and every still is grey `(128,128,128)` except a daylight-tinted steel area `(110,150,200)` covering 30% of the zone
- **THEN** the score is 0, no still is open, and the event is not a door opening

#### Scenario: Weakly blue pixels do not count
- **WHEN** no setup result is stored, zones are `0.0,0.0,1.0,1.0`, and a still is grey except a teal `(40,150,200)` block covering 10% of the zone (strongly colorful, but blue leads by only 50)
- **THEN** that block does not count and the still is not open

### Requirement: Door event record
For each door opening, the system SHALL save one door event under the account with the device ID, Ring event ID, `opened_at`, `closed_at` (ISO 8601 UTC), `duration_s`, the still keys, and a `status`. `opened_at` SHALL be the request time of the opening's first open still. `closed_at` SHALL be the request time of the first still after the opening's last open one, or the window end when no still follows it. `duration_s` SHALL be `closed_at − opened_at` in whole seconds, rounded. An event saved with `status = "no_media"` because too few stills were downloaded SHALL take `opened_at` and `closed_at` from the window. A second run for the same Ring event SHALL NOT create a second record or a second analysis.

#### Scenario: Door event saved
- **WHEN** the window is 1786715596000–1786715621000, 25 stills are downloaded, and stills 6 to 15 are open
- **THEN** a door event exists with `opened_at = "2026-08-14T13:53:21.769Z"`, `closed_at = "2026-08-14T13:53:31.384Z"`, `duration_s = 10` and `status = "analyzing"` before analysis starts

#### Scenario: Two openings in one window
- **WHEN** the window is 1786715596000–1786715626000, 30 stills are downloaded, and stills 3–6 and 20–24 are open
- **THEN** two door events exist: the first runs from still 3's request time to still 7's, and the second from still 20's to still 25's, each with its own `duration_s`

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
While face blurring is on (the default, see `face-blur-setting`), before a still is stored the system SHALL send it (after cropping, if a crop box is configured) to face detection and SHALL blur every face reported, whatever its confidence. Each face box (fractions of the image sent to detection) SHALL be enlarged by 30% about its centre, clipped to the image, and made unrecognizable. With no crop box and no faces, the still SHALL be stored byte for byte as downloaded. While face blurring is off, face detection SHALL NOT be called. The still SHALL be stored cropped (if a crop box is configured) and otherwise as downloaded.

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

#### Scenario: Blurring off, no crop box
- **WHEN** face blurring is off, no crop box is configured, and a door opening's 4 stills are downloaded
- **THEN** face detection is never called, each `still-<n>.jpg` is byte for byte the downloaded still, and no `face_detect_cost` line is logged

#### Scenario: Blurring off, with a crop box
- **WHEN** face blurring is off and a crop box is configured
- **THEN** each stored still is the cropped JPEG, and face detection is never called

### Requirement: Fail closed when face detection fails
While face blurring is on, if face detection fails for a still (any service error, throttling, timeout, or an image it rejects), the system SHALL drop that still: nothing is stored for it as an event still, it does not count toward the stills downloaded, and a `face_detect_failed` warning is logged with the still number and the error code. While face blurring is on, an unblurred still SHALL never be stored or sent to analysis. The only copy that may be stored is the owner-only debug trace's `debug/raw-<n>.jpg`, a blurred thumbnail at most 160 px on its longest side, written only while `DEBUG_TRACES` is on and expiring with the bucket's 7-day lifecycle.

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
- **WHEN** face blurring and `DEBUG_TRACES` are on and face detection fails for still 2
- **THEN** `debug/raw-2.jpg` may exist as a blurred thumbnail at most 160 px on its longest side, no stored object holds still 2's downloaded bytes, and `still_keys` does not list it

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
The item analysis SHALL use only the stored stills: blurred and, if configured, cropped while face blurring is on; cropped only while it is off. No still SHALL be sent to the analysis model other than the stored object. The door check reads the downloaded, uncropped stills in memory. While face blurring is on, the owner-only debug trace keeps only blurred thumbnails of them.

#### Scenario: Analysis receives blurred bytes
- **WHEN** a door opening's still 1 had a face blurred and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes or `debug/raw-<n>.jpg`

#### Scenario: Door check runs on downloaded stills
- **WHEN** face blurring is on and a downloaded still passes the door check and contains a face
- **THEN** the event counts as a door opening, face detection is called only after the door check, and the only full-size stored still is the blurred one

#### Scenario: No debug stills when tracing is off
- **WHEN** face blurring is on, `DEBUG_TRACES=false` and a downloaded still contains a face
- **THEN** no copy of it is stored anywhere except its blurred event still

#### Scenario: Analysis while blurring is off
- **WHEN** face blurring is off and a door opening goes on to analysis
- **THEN** the image bytes for each still in the analysis request equal the stored `still-<n>.jpg`

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
For a door opening found in the clip, `opened_at` SHALL be the time of the opening's first open frame. `closed_at` SHALL be the time of the first closed frame after the opening's last open frame, or `end_ms` if no closed frame follows. `duration_s` SHALL be their difference, rounded to whole seconds.

#### Scenario: Open and close times
- **WHEN** the window starts at 1786715596000 and the frames at offsets 4000–12000 ms are open while the frame at 12500 ms is closed
- **THEN** the door event has `opened_at = "2026-08-14T13:53:20.000Z"`, `closed_at = "2026-08-14T13:53:28.500Z"` and `duration_s = 8`

#### Scenario: Two openings in one clip
- **WHEN** the window is 1786715596000–1786715626000, the frames at offsets 1000–5500 ms and 18000–23500 ms are open, and every other frame is closed (12 s from offset 6000 to 18000 ms)
- **THEN** two door events exist: the first has `opened_at = "2026-08-14T13:53:17.000Z"`, `closed_at = "2026-08-14T13:53:22.000Z"` and `duration_s = 5`; the second has `opened_at = "2026-08-14T13:53:34.000Z"`, `closed_at = "2026-08-14T13:53:40.000Z"` and `duration_s = 6`

#### Scenario: Brief closed run in one opening
- **WHEN** the frames at offsets 4000–8000 ms and 12000–14000 ms are open and the frames in between are closed (3.5 s from offset 8500 to 12000 ms)
- **THEN** one door event exists, with `opened_at` at offset 4000 ms and `closed_at` at offset 14500 ms

#### Scenario: Still open at the end of the clip
- **WHEN** the window is 1786715596000–1786715616000 and every frame from offset 15000 ms to the last one is open
- **THEN** `closed_at` is `"2026-08-14T13:53:36.000Z"` (the window end)

### Requirement: Stills for an opening found in the clip
For each door opening found in the clip, the system SHALL pick up to 4 frames from that opening's open span. The span runs from the opening's first open frame through the first closed frame after its last open one. The picks are evenly spaced and always include the span's first and last frame. Each picked clip frame, encoded as JPEG, SHALL be used as that still; the system SHALL NOT request Ring stills for them, since Ring's still at a timestamp can show a different moment than the frame the door check scored. These stills are then cropped, face-blurred, stored as `still-<n>.jpg` and analyzed exactly as stills are today.

#### Scenario: Four stills from the open span
- **WHEN** the frame interval is 500 ms, the frames at offsets 4000–12000 ms are open and the frame at 12500 ms is closed
- **THEN** the clip frames at offsets 4000, 7000, 9500 and 12500 ms are face-blurred and stored as `still-1.jpg` … `still-4.jpg`

#### Scenario: Short open span
- **WHEN** only the frame at offset 6000 ms is open and the frame at 6500 ms is closed
- **THEN** exactly two stills are stored, the clip frames at offsets 6000 and 6500 ms

#### Scenario: Stills from each opening
- **WHEN** the frame interval is 500 ms and the frames at offsets 1000–5500 ms and 18000–23500 ms are open
- **THEN** the first door event's stills are the frames at 1000, 2500, 4500 and 6000 ms under `events/<start_ms>/`, and the second's are the frames at 18000, 20000, 22000 and 24000 ms under `events/<start_ms>/opening-2/`

#### Scenario: No Ring still requested
- **WHEN** a door opening is found in the clip and Ring would answer still requests with a closed-door image
- **THEN** no request is made to `POST /v1/devices/{device_id}/media/image/download`, and each stored still is the JPEG clip frame (the lit frame at offset 7000 ms for `still-2.jpg`), not Ring's image

#### Scenario: Still missing, frame used
- **WHEN** Ring would answer 403 for a still at `start_ms` + 7000 ms
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
The full event clip SHALL only be held in memory or in a temporary file in Lambda `/tmp`. The temporary file SHALL be deleted when the step ends, whether it succeeds or fails. The only clip objects written to S3 SHALL be a door opening's open-span `clip.mp4` and, while face blurring is on, its transient `clip-raw.mp4` (see `clip-face-blur`). Apart from those clips, the stored stills and the debug-trace frames, no frame SHALL be written to S3.

#### Scenario: Door opening processed
- **WHEN** a door opening is processed from a clip with debug traces off and face blurring off
- **THEN** the only S3 objects written are `still-<n>.jpg` and one `clip.mp4`, and `clip.mp4` is shorter than the event clip

#### Scenario: Door opening processed with blurring on
- **WHEN** a door opening is processed from a clip with debug traces off and face blurring on, and the blur step succeeds
- **THEN** after the run the only S3 objects under the event's prefix are `still-<n>.jpg` and one `clip.mp4`, and no `clip-raw.mp4` remains

#### Scenario: Temporary file removed on error
- **WHEN** decoding fails partway through the clip
- **THEN** the temporary clip file no longer exists after the step

#### Scenario: Temporary file removed after the cut
- **WHEN** a door opening's clip is cut and stored
- **THEN** neither the downloaded clip nor the cut leaves a file behind in the clip directory

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

### Requirement: Open-span clip stored
For a door opening found in the event clip, the system SHALL cut the clip to the open span (`opened_at` → `closed_at`) without re-encoding. The cut SHALL start at the last keyframe at or before `opened_at`. `clip_span = [start_s, end_s]` is where the open span starts and ends in the cut, in seconds rounded to 0.1. While face blurring is off, the system SHALL store the cut as `clip.mp4` under the same prefix as the event's stills and SHALL record `clip_key` and `clip_span` on the door event. While face blurring is on, it SHALL instead store the cut as `clip-raw.mp4` tagged `transient=true`, SHALL NOT set `clip_key`, and SHALL pass `raw_key` and `clip_span` on in the step output for the clip blur step. A failed cut or upload SHALL be logged as `clip_not_stored` with a reason and SHALL NOT fail the step or change its outcome.

#### Scenario: Clip cut to the open span
- **WHEN** face blurring is off, the event clip has keyframes every 2.0 s, the open span runs from offset 4500 ms to 12500 ms, and the door check outcome is `door_open`
- **THEN** `clip.mp4` is stored under the stills prefix, starts at the 4.0 s keyframe, ends at or after 12.5 s and lasts under 9.0 s, and the door event has `clip_key` set to its key and `clip_span = [0.5, 8.5]`

#### Scenario: Raw clip while blurring is on
- **WHEN** face blurring is on and the same clip is processed
- **THEN** `clip-raw.mp4` is stored under the stills prefix with tag `transient=true`, no `clip.mp4` is written by this step, the door event has no `clip_key`, and the step output has `clip.raw_key` set to its key and `clip.clip_span = [0.5, 8.5]`

#### Scenario: Door still open at the end of the clip
- **WHEN** the last clip frame is open
- **THEN** the stored clip runs to the end of the event clip and `clip_span` ends at its length

#### Scenario: Cut fails
- **WHEN** remuxing the clip raises a decode error
- **THEN** `clip_not_stored` is logged with `reason = "cut_failed"`, the door event has no `clip_key`, the step output has no `clip`, the stills are stored, and the outcome is still `door_open`

#### Scenario: Upload fails
- **WHEN** S3 rejects the `clip.mp4` or `clip-raw.mp4` upload
- **THEN** `clip_not_stored` is logged with `reason = "upload_failed"`, the door event has no `clip_key`, the step output has no `clip`, and analysis goes ahead

#### Scenario: No clip on the fallback path
- **WHEN** the clip is unavailable and the door check samples stills across the window
- **THEN** no `clip.mp4` or `clip-raw.mp4` is written and the door event has no `clip_key`

#### Scenario: Not a door opening
- **WHEN** the outcome is `not_door`
- **THEN** no `clip.mp4` or `clip-raw.mp4` is written

### Requirement: Signed media readable cross-origin
The stills bucket SHALL have a CORS rule that allows `GET` and `HEAD` from any origin, allows the `Range` request header, and exposes `Content-Length`, `Content-Range` and `Accept-Ranges`, so the app can draw a clip frame onto a canvas. The bucket SHALL stay private: every read still needs a presigned link.

#### Scenario: CORS rule on the stills bucket
- **WHEN** the stack is synthesized
- **THEN** the stills bucket's `CorsConfiguration` has one rule with `AllowedMethods` `["GET", "HEAD"]`, `AllowedOrigins` `["*"]`, `AllowedHeaders` including `Range`, and `ExposedHeaders` `Content-Length`, `Content-Range` and `Accept-Ranges`

#### Scenario: Bucket still private
- **WHEN** the stack is synthesized
- **THEN** the stills bucket still blocks all public access and has no bucket policy statement that allows unsigned reads

### Requirement: Clip blur step in the workflow
After `Save` succeeds, the workflow SHALL run the clip blur step when the state has `clip.raw_key`, and SHALL go straight to `Done` otherwise. Any error from the blur step SHALL be caught by a `DropRawClip` step that deletes `clip-raw.mp4` and logs `clip_not_stored` with `reason = "blur_failed"`. After that the run SHALL still end in `Done`, never in `AnalysisFailed`.

#### Scenario: Blur runs after save
- **WHEN** a run with `clip.raw_key` set completes `Save`
- **THEN** the next state is `BlurClip`, and then `Done`

#### Scenario: No raw clip
- **WHEN** a run without `clip.raw_key` completes `Save`
- **THEN** `BlurClip` is not entered and the run ends in `Done`

#### Scenario: Blur error caught
- **WHEN** `BlurClip` fails with `States.ALL`
- **THEN** `DropRawClip` runs and the run ends in `Done`

### Requirement: Blocked suspect clips leave the streak unchanged
For a suspect clip with a stored closed anchor, the system SHALL check each bookend (the first and last checked frames) that reads open. At such a bookend, a zone that reads open *looks closed* when the mean absolute difference between the bookend's edge map and the anchor inside the zone's box (after the event's alignment shift, at 128×72), divided by 255, is at most `ZONE_CLOSED_MAX_DIFF` (default 0.05). The clip SHALL be *blocked* when it has at least one open bookend and no open-reading zone at any open bookend looks closed. A blocked clip SHALL leave `suspect_streak` unchanged and SHALL log `door_check_blocked` with `frames`, `open_share` and `zones_source`. Every other suspect clip SHALL add 1 to the streak, as before. A blocked clip SHALL otherwise be handled as any suspect clip: re-scored with the fridge light, `suspect = true` in the run output, and no self-tuning sample.

#### Scenario: Person in front of the zones at both bookends
- **WHEN** setup rules read every frame of a 41-frame clip open, and at both bookends the zone's edge difference from the anchor is 0.15
- **THEN** the clip is blocked, `suspect_streak` stays 2 (its value before), a `door_check_blocked` line is logged, and the outcome comes from the fridge-light re-score

#### Scenario: Wrong rules on a clear view
- **WHEN** setup rules read every frame of a 41-frame clip open, and at the first bookend the zone's edge difference from the anchor is 0.01
- **THEN** the clip is not blocked and `suspect_streak` goes from 2 to 3

#### Scenario: One bookend clear is enough to count
- **WHEN** both bookends read open, the first bookend's zone differs from the anchor by 0.15 and the last bookend's zone by 0.02
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: Two zones, only the open one is checked
- **WHEN** at both bookends zone A reads open and differs from the anchor by 0.12, and zone B reads closed and differs by 0.0
- **THEN** the clip is blocked

#### Scenario: Shift applied to the zone box
- **WHEN** the event aligned with a shift of 4 px right and the bookend is the anchor's view moved 4 px right, with the rules reading it open
- **THEN** the zone looks closed (difference ≤ 0.05) and the clip counts toward the streak

#### Scenario: Suspect by share alone
- **WHEN** a 100-frame clip is closed at frames 1–8 and 100 and open in between under setup rules (so it is suspect by its open share, with no open bookend)
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: No anchor stored
- **WHEN** a suspect clip comes from a device whose setup has no anchor
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: Recorded clip with the owner in front
- **WHEN** the anchor is the recorded closed reference fixture, the bookends are the recorded first and last frames from 2026-10-18, and the rules are the prod setup's three `change` zones reading open
- **THEN** the clip is blocked

### Requirement: One door event per opening in a motion
Each opening in a motion SHALL be recorded as its own door event, numbered k = 1, 2, … in time order. Opening 1 SHALL use `sk = DOOR#<iso window start>#<device_id>` and the stills prefix `accounts/<account_id>/devices/<device_id>/events/<start_ms>/`. Opening k ≥ 2 SHALL use `DOOR#<iso window start>#<device_id>#<k>` and the prefix `…/events/<start_ms>/opening-<k>/`. Its stills, `clip.mp4`, `clip-raw.mp4` and `analysis.mp4` SHALL be built only from its own span and stored under its own prefix.

#### Scenario: Keys per opening
- **WHEN** the window starts at 1786715596000 on device `D1` and the clip shows two openings with a 13 s closed gap between them
- **THEN** the door events have `sk` `DOOR#2026-08-14T13:53:16.000Z#D1` and `DOOR#2026-08-14T13:53:16.000Z#D1#2`, and the second one's `still_keys`, `clip_key` and the `analysis_video.key` in its step output all start with `accounts/A1/devices/D1/events/1786715596000/opening-2/`

#### Scenario: Media from its own span only
- **WHEN** face blurring is on and the clip shows openings at offsets 1000–5500 ms and 18000–23500 ms
- **THEN** each opening's `clip-raw.mp4` covers only its own span (`clip_span` ends within 1 s of that span's close), each `analysis.mp4` starts at most one frame before its own span, and each opening's `still_ms` lies inside its own span

#### Scenario: Each opening has its own status
- **WHEN** the first opening's stills all fail face detection and the second's are stored
- **THEN** the first door event is saved with `status = "no_media"`, the second with `status = "analyzing"`, the outcome is `door_open`, and `openings` holds only the second

### Requirement: All openings claimed together
All door events of one motion SHALL be written in one transaction together with the motion's single Ring-event claim. A second run for the same Ring event SHALL create no door event, SHALL delete every raw clip it uploaded, and SHALL end with `duplicate`.

#### Scenario: Two openings in a re-run
- **WHEN** a motion with two openings has been recorded and a second run resolves to the same Ring event
- **THEN** the table still holds exactly two door events for it, no `clip-raw.mp4` from the second run remains, and the outcome is `duplicate`

### Requirement: Openings handed to analysis
For outcome `door_open`, the fetch-stills output SHALL hold `openings`: one entry per door event with `status = "analyzing"`, in time order. Each entry is the full step state for that opening (`door_sk`, `still_keys`, `still_ms`, and `clip` and `analysis_video` when present). The output's top-level fields SHALL equal its first entry's.

#### Scenario: Output for two openings
- **WHEN** a clip shows two openings and both store 4 stills
- **THEN** the output has `outcome = "door_open"`, `openings` has 2 entries with different `door_sk`, and the top-level `door_sk`, `still_keys` and `still_ms` equal `openings[0]`'s

#### Scenario: Output for one opening
- **WHEN** a clip shows one opening
- **THEN** `openings` has 1 entry equal to the top-level door event fields

### Requirement: Each opening analyzed in turn
After `IsDoorOpening`, the workflow SHALL run Analyze → Save → clip blur once for each entry in `openings`, one at a time, in order. A failure in one opening SHALL mark only that door event `analysis_failed`, and SHALL NOT stop the later openings. After all openings, the run SHALL end in `Done` when none failed, and otherwise in `AnalysisFailed`.

#### Scenario: Openings run one at a time
- **WHEN** the stack is synthesized
- **THEN** a Map state reads items from `$.openings` with `MaxConcurrency = 1`, and its iterator starts at `Analyze`

#### Scenario: One opening fails
- **WHEN** the first opening's analysis fails after its retries and the second succeeds
- **THEN** the first door event is `analysis_failed`, the second is saved, and the run ends in the `AnalysisFailed` Fail state

#### Scenario: All openings succeed
- **WHEN** every opening's Save succeeds
- **THEN** the run ends in `Done`

### Requirement: Door check follows the camera
Before scoring an event's frames or stills, the door check SHALL align them with the device's closed anchor and use the resulting rules, as set out in `door-self-calibration`. After the event is claimed, or found not to be a door opening, it SHALL store the event's sample and re-tune. A failure in alignment, sampling or re-tuning SHALL be logged and SHALL NOT change the event's outcome. The event's debug trace SHALL record the shift, the alignment error, and whether tuned rules were used.

#### Scenario: Shifted camera still detects the opening
- **WHEN** setup was run on frames where the door zone is at `x = 0.38`, and the event clip is the same scene shifted 6 px right at 128×72 with the door opening in frames 4–8
- **THEN** alignment succeeds with `dx ≈ 0.047`, the shifted zone scores frames 4–8 as open, and the outcome is `door_open`

#### Scenario: Same clip without alignment misses it
- **WHEN** the same shifted clip is checked with alignment turned off (no anchor stored)
- **THEN** the outcome is `not_door`

#### Scenario: Alignment error does not drop an opening
- **WHEN** reading the alignment from the table raises an error
- **THEN** the event is checked with the unshifted rules, a `door_alignment_unavailable` warning is logged, and the outcome is decided as before

#### Scenario: Re-tune failure after a claimed opening
- **WHEN** the door event is claimed and storing the sample raises an error
- **THEN** the outcome is still `door_open` and a `door_sample_failed` warning is logged

#### Scenario: Trace records the shift
- **WHEN** an event aligns with shift `(0.016, 0)`, error 0.031, and tuned rules are in use
- **THEN** the door trace has `alignment = {"dx": 0.016, "dy": 0, "error": 0.031, "ok": true}` and `rules = "tuned"`

### Requirement: Runs for a paused camera stop before any download
When a workflow run reaches the stills step and its account and device are paused (see the `fridge-monitoring` capability), the step SHALL return outcome `paused` without downloading stills or the clip from Ring, without face detection, and without claiming or recording a door event. The run SHALL then end without analysis, so no inventory change, open/close stat or Nova cost is recorded.

#### Scenario: Paused after the run started
- **WHEN** a run for device D1 started while it was active, and the owner paused D1 before the stills step
- **THEN** the step returns `outcome: "paused"`, no Ring media request is made, no face detection is called, no `DOOR#` item is written, and the run ends in `NoAnalysis`

#### Scenario: Resumed before the stills step
- **WHEN** D1 was paused and resumed before the stills step
- **THEN** the stills step runs the door check as usual

### Requirement: Suspect clip detected
When the door check runs on an event clip with the device's setup rules (`zones_source` is `"setup"`, or `"tuned"` after self-tuning) and at least 10 frames were checked, the clip SHALL count as *suspect* when its first and last checked frames are both open, or when at least 90% of its checked frames are open. A clip with fewer than 10 checked frames, or checked with the default rules, is never suspect.

#### Scenario: Every frame open
- **WHEN** setup rules are used and all 41 checked frames of a 20.5 s clip are open
- **THEN** the clip is suspect and a `door_check_suspect` log line records `frames = 41`, `open_share = 1.0` and `zones_source = "setup"`

#### Scenario: Open at both ends
- **WHEN** setup rules are used, a clip has 40 frames, and frames 1–3 and 38–40 are open while the rest are closed
- **THEN** the clip is suspect

#### Scenario: Normal opening
- **WHEN** setup rules are used and a 54-frame clip is open only at frames 18–26
- **THEN** the clip is not suspect and no `door_check_suspect` line is logged

#### Scenario: Long opening that starts closed
- **WHEN** setup rules are used and a 100-frame clip is closed at frames 1–8 and open from frame 9 to frame 100
- **THEN** the clip is suspect (92% open), and is re-scored as set out in "Suspect clip re-scored with the fridge light"

#### Scenario: Short clip
- **WHEN** setup rules are used and all 8 checked frames are open
- **THEN** the clip is not suspect

#### Scenario: Default rules
- **WHEN** no setup result is stored and every checked frame is open
- **THEN** the clip is not suspect

#### Scenario: Tuned rules
- **WHEN** the device's rules were re-tuned (`zones_source = "tuned"`) and all 41 checked frames are open
- **THEN** the clip is suspect

### Requirement: Suspect clip re-scored with the fridge light
For a suspect clip, the door check SHALL score the same frames again with one rule per setup zone: that zone's box (after the event's alignment shift) with feature `blue`, direction `above`, and threshold `DOOR_THRESHOLD` (else 0.01). This second result SHALL decide the outcome, the open span, the open and close times and the picked stills. The `motion_not_door` or `door_event_recorded` log line SHALL have `zones_source = "fallback"`, and the run output SHALL have `suspect = true`.

#### Scenario: Fridge light finds the real opening
- **WHEN** a 54-frame clip is suspect under the setup rules, and with the fridge-light rule only frames 18–26 are open (blue-lit fraction 0.045 to 0.059, the rest 0.0)
- **THEN** the outcome is `door_open`, `opened_at` is the time of frame 18, `closed_at` is the time of frame 27, the stills are picked from frames 18–27, and the log line has `zones_source = "fallback"`

#### Scenario: Fridge light finds no opening
- **WHEN** a 41-frame clip is suspect and no frame is open with the fridge-light rule (a person walks past with the doors closed)
- **THEN** the outcome is `not_door`, no door event is recorded, there is no face detection, S3 write or analysis, and the `motion_not_door` line has `zones_source = "fallback"`

#### Scenario: Not suspect keeps the setup result
- **WHEN** the clip is not suspect
- **THEN** the setup rules' result is used unchanged and the run output has no `suspect` field

### Requirement: Suspect events teach nothing
A suspect event SHALL NOT be recorded as a self-tuning sample and SHALL NOT trigger a re-tune of the door rules, whatever its outcome.

#### Scenario: No sample from a suspect event
- **WHEN** a suspect event's alignment succeeds
- **THEN** no `DOORSAMPLE#{device}#…` item is written for it and the setup's tuned rules are unchanged

#### Scenario: Normal event still samples
- **WHEN** an event that is not suspect aligns successfully
- **THEN** a sample is recorded as before

### Requirement: Suspect streak per device
The system SHALL keep, per account and device, the number of suspect events in a row (`suspect_streak`). A suspect event SHALL add 1. An event checked on its clip with setup rules that is not suspect SHALL reset it to 0. A successful setup run SHALL reset it to 0. Events that fall back to stills, or use the default rules, SHALL leave it unchanged.

#### Scenario: Three suspect events in a row
- **WHEN** three suspect events follow each other for the device
- **THEN** its `suspect_streak` is 3

#### Scenario: Normal event resets the streak
- **WHEN** `suspect_streak` is 2 and the next clip checked with setup rules is not suspect
- **THEN** `suspect_streak` is 0

#### Scenario: Setup run resets the streak
- **WHEN** `suspect_streak` is 5 and the owner runs setup successfully
- **THEN** `suspect_streak` is 0

#### Scenario: Streak write fails
- **WHEN** writing the streak raises a table error
- **THEN** a `suspect_streak_failed` warning is logged and the event's outcome is unchanged
