# Spec Delta

## MODIFIED Requirements

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
- **WHEN** Ring answers 425 `RECORDING_NOT_READY`, 416 `MEDIA_NOT_FOUND` or 206, either to the clip request or to the `Location` download after a 303, and then a later attempt returns the MP4
- **THEN** the whole request (POST, then link) is repeated after waits of 3, 6 and 12 s, and the door check runs on the clip's frames, up to 4 attempts in total

#### Scenario: Partial content on the link
- **WHEN** Ring answers 303 to the clip request, the `Location` download answers 206, and the second attempt's download answers 200 with the MP4
- **THEN** the clip request is made twice, with one 3 s wait between, and the door check runs on the clip's frames

#### Scenario: Partial content on the request
- **WHEN** Ring answers the clip request with 206 and the second request with 303 to an MP4
- **THEN** the clip request is made twice and the door check runs on the clip's frames

#### Scenario: Not a door opening
- **WHEN** no frame passes the door check
- **THEN** the outcome is `not_door`, no still is requested, and there is no face detection, S3 write or analysis

#### Scenario: Short opening between stills
- **WHEN** a 121.9 s clip shows the door open only from 63.7 s to 66.7 s
- **THEN** the outcome is `door_open`, although 30 stills spread across the window would all fall outside the opening

### Requirement: Fall back to still sampling without the clip
If the clip can't be used, the system SHALL log `clip_unavailable` with the device ID, a `reason` and, for a `status_<code>` reason, the `stage` that answered it (`request` for the clip request, `link` for the `Location` download). For a link answer it SHALL also log `content_range` and `content_length` from the response headers when present. The pre-signed link itself SHALL NOT be logged. Then it SHALL run the door check on sampled stills as it does today. The reasons are: `status_<code>` (any other HTTP status from the request or the link, or 425/416/206 after 4 attempts), `download_failed` (Ring, OAuth or network error), `too_large` (more than 300 MB), `decode_failed` (not a readable video) and `no_frames` (no frame at offset 0). A clip problem SHALL NOT make the step fail or drop a door opening.

#### Scenario: Ring refuses the clip
- **WHEN** Ring answers the clip request with 403
- **THEN** `clip_unavailable` is logged with `reason = "status_403"` and `stage = "request"`, and the door check runs on stills as before

#### Scenario: Clip never ready
- **WHEN** Ring answers 303 to all 4 clip requests and each `Location` download answers 416 `MEDIA_NOT_FOUND`
- **THEN** `clip_unavailable` is logged with `reason = "status_416"` and `stage = "link"` after waits of 3, 6 and 12 s, and the door check runs on stills

#### Scenario: Clip only ever partial
- **WHEN** Ring answers 303 to all 4 clip requests and each `Location` download answers 206 with `Content-Range: bytes 0-1023/52000` and `Content-Length: 1024`
- **THEN** `clip_unavailable` is logged with `reason = "status_206"`, `stage = "link"`, `content_range = "bytes 0-1023/52000"` and `content_length = "1024"`, and the door check runs on stills

#### Scenario: Clip request never ready
- **WHEN** Ring answers 425 to all 4 clip requests
- **THEN** `clip_unavailable` is logged with `reason = "status_425"` and `stage = "request"`, and the door check runs on stills

#### Scenario: Unreadable clip
- **WHEN** the `Location` download returns bytes that are not a video
- **THEN** `clip_unavailable` is logged with `reason = "decode_failed"`, and the door check runs on stills

#### Scenario: Clip too large
- **WHEN** the clip download announces or streams more than 300 MB
- **THEN** the download stops, `clip_unavailable` is logged with `reason = "too_large"`, and the door check runs on stills

#### Scenario: Network error
- **WHEN** the clip request raises a network error
- **THEN** `clip_unavailable` is logged with `reason = "download_failed"`, and the door check runs on stills

