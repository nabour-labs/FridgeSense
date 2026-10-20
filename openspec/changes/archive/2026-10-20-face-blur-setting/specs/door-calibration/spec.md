# Spec Delta

## MODIFIED Requirements

### Requirement: Camera snapshot
`POST /api/camera/snapshot` SHALL request a still for the linked account's first discovered device at the current time minus 3 s (`POST /v1/devices/{device_id}/media/image/download` with `type = "at_timestamp"`). It SHALL follow the redirect without the `Authorization` header. While face blurring is on (the default, see `face-blur-setting`), it SHALL blur every face in the still as door-event stills are blurred. While it is off, it SHALL NOT call face detection. It SHALL scale the still down to at most 960 px wide keeping its aspect ratio, and answer 200 `{"image": "<base64 JPEG>", "captured_at": "<ISO 8601 UTC>"}`. The image SHALL be at most 300,000 bytes. The snapshot SHALL NOT be stored. A still that is not ready (Ring 416 or 425) SHALL be requested once more after 2 s. When both attempts find no footage, the route SHALL fall back to the newest motion event in the device's Ring history (`GET /v1/history/devices/{device_id}/events?event_types=motion`, largest `start`) and request one still at the middle of that event (its `start` when it has no `end`); `captured_at` is then that time. The camera only records when something moves, so without this fallback a snapshot works only while someone stands in front of it.

#### Scenario: Snapshot taken
- **WHEN** the owner calls the route at 2026-10-15T19:20:10Z and Ring answers 303 with a link to a 1920×1080 JPEG with no faces
- **THEN** Ring is asked for timestamp 1792092007000, the response's `image` decodes to a 960×540 JPEG of at most 300,000 bytes, `captured_at = "2026-10-15T19:20:07.000Z"`, and nothing is written to the table or S3

#### Scenario: Face blurred in the snapshot
- **WHEN** face blurring is on and face detection reports a face at `(0.40, 0.20, 0.20, 0.30)` in the still
- **THEN** the returned image is blurred inside that face's enlarged box

#### Scenario: Snapshot while blurring is off
- **WHEN** face blurring is off and Ring returns a 1920×1080 still
- **THEN** face detection is not called and the response is 200 with a 960×540 image

#### Scenario: Snapshot from the latest motion event
- **WHEN** Ring answers 416 `MEDIA_NOT_FOUND` to both attempts at now − 3 s, and the device's history lists motion events starting 1786711000000 and 1786715596000 (ending 1786715621000)
- **THEN** one more still is requested at 1786715608500, the response is 200 with that image, and `captured_at = "2026-08-14T13:53:28.500Z"`

#### Scenario: No recent footage
- **WHEN** Ring answers 416 `MEDIA_NOT_FOUND` to both attempts and the device's history has no motion events, cannot be read, or has no still at the newest event
- **THEN** the response is 409 `{"error": "no recent footage"}`

#### Scenario: Camera or face detection unavailable
- **WHEN** Ring answers 500, the Ring token cannot be refreshed, or face blurring is on and face detection fails
- **THEN** the response is 502 `{"error": "camera unavailable"}` and no unblurred image is returned

#### Scenario: No device discovered
- **WHEN** the account is linked but no device has been discovered
- **THEN** the snapshot and every door-calibration route answer 409 `{"error": "no camera found"}`
