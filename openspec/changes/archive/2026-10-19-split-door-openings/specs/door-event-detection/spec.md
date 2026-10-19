## MODIFIED Requirements

### Requirement: Door-open check before any analysis
The system SHALL decide for each downloaded still whether it is *open*, using rules for zones, each a box of fractions `x, y, width, height` of the downloaded still.
- **With a setup result** stored for the event's account and device (see the `door-calibration` capability), each zone has its own feature (`blue`, `color`, `brightness` or `change`, measured as setup measures it, against the stored baseline for `change`), direction and threshold. A still is open when, in any zone, the feature's value is at or above the threshold (direction `above`) or at or below it (direction `below`).
- **Without a setup result**, every zone uses `blue` with direction `above`: the fraction of pixels that are both colorful (`max(R,G,B) − min(R,G,B) > 60` and `max(R,G,B) > 100`) and blue-lit (`B − max(R,G) > 20`), as the fridge's LED-lit interior is. Warm colors such as food held in front of the closed doors do not count. The zones are `DOOR_ZONES`, else the defaults `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers), and the threshold is `DOOR_THRESHOLD`, else 0.01.

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

## ADDED Requirements

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
