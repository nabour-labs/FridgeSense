# Spec Delta

## ADDED Requirements

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
- **WHEN** Ring answers the clip request with 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND`, then with 303
- **THEN** the clip is requested again and the door check runs on its frames, up to 3 attempts in total

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
If the clip can't be used, the system SHALL log `clip_unavailable` with the device ID and a `reason`, then run the door check on sampled stills as it does today. The reasons are: `status_<code>` (any other HTTP status, or 425/416 after 3 attempts), `download_failed` (Ring, OAuth or network error), `too_large` (more than 300 MB), `decode_failed` (not a readable video) and `no_frames` (no frame at offset 0). A clip problem SHALL NOT make the step fail or drop a door opening.

#### Scenario: Ring refuses the clip
- **WHEN** Ring answers the clip request with 403
- **THEN** `clip_unavailable` is logged with `reason = "status_403"`, and the door check runs on stills as before

#### Scenario: Clip never ready
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
