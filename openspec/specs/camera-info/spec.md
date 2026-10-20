# camera-info Specification

## Purpose
Shows what the app knows about the connected fridge camera: its details as Ring reports them, whether it is online now, its recorded online/offline history and uptime, and the browser's video decoder.

## Requirements

### Requirement: Camera details from Ring
`GET /api/camera` SHALL return the account's first camera, read from Ring with `GET /v1/devices/{id}?include=status,capabilities,configurations,location`. Every signed-in role, viewers included, MAY read it. The body SHALL have `device_id`, `name`, `image_url`, `manufacturer` ("Ring"), `online`, `video`, `image_enhancements`, `motion_detection`, `e2e_encryption`, `location`, `history`, `uptime` and `checked_at` (ISO 8601).

#### Scenario: Camera details
- **WHEN** a viewer requests `GET /api/camera` and Ring answers with the recorded `device_detail.json` fixture (name "Fridge Cam", online true, codecs `["AVC"]`, ratio "16:9", max resolution 1080)
- **THEN** the response is 200 with `name: "Fridge Cam"`, `manufacturer: "Ring"`, `online: true`, `video: {codecs: ["AVC"], ratio: "16:9", max_resolution: 1080, supported_resolutions: [1080]}`, and the fixture's `image_url`

#### Scenario: Image enhancements supported and on
- **WHEN** the fixture's capabilities list `color_night_vision`, `hdr`, `ir_led_night_vision` and `privacy_zones`, and its configurations set `hdr: "on"` and the others `"off"`
- **THEN** `image_enhancements` is `[{name: "color_night_vision", on: false}, {name: "hdr", on: true}, {name: "ir_led_night_vision", on: false}]` (privacy zones are not an on/off setting and are left out)

#### Scenario: Supported capability without an on/off setting
- **WHEN** Ring answers with the recorded `device_detail_recorded.json` (capabilities `ir_led_night_vision`, `privacy_zones` and `snapshot`; configurations with `ir_led_night_vision: "off"` plus `hdr`, `color_night_vision` and `auto_zoom_track`, which the camera does not list as supported)
- **THEN** `image_enhancements` is `[{name: "ir_led_night_vision", on: false}]`: `snapshot` has no on/off setting and is left out, and settings the camera does not support are not shown. With no configurations at all, each supported non-zone enhancement is listed with `on: null`

#### Scenario: Motion detection and encryption
- **WHEN** the fixture's configurations have `motion_detection.enabled: "on"` and `e2e_encryption.enabled: false`
- **THEN** `motion_detection` is `true` and `e2e_encryption` is `false`

#### Scenario: Coarse location
- **WHEN** the fixture includes a `locations` resource
- **THEN** `location` holds that resource's string attributes unchanged, and is `null` when Ring includes no location

#### Scenario: No camera linked
- **WHEN** the account has no discovered device
- **THEN** the response is 409 `{"error": "no camera linked"}`

### Requirement: Camera details when Ring is unreachable
If Ring cannot be reached or answers non-200, `GET /api/camera` SHALL still answer 200 with the stored device name, `online: null`, `video`, `image_enhancements`, `motion_detection`, `e2e_encryption` and `location` all `null`, the recorded history and uptime, and `ring: "unavailable"`. It SHALL record no status change.

#### Scenario: Ring down
- **WHEN** Ring answers `GET /v1/devices/{id}` with 503
- **THEN** the response is 200 with `name` from the stored device, `online: null`, `video: null`, `ring: "unavailable"`, and the recorded history

#### Scenario: Ring token rejected
- **WHEN** the token refresh fails with an auth error
- **THEN** the response is 200 with `ring: "unavailable"` and no status change is stored

### Requirement: Status change recorded on read
When Ring reports `online` and it differs from the latest recorded status change for that device, or none is recorded, `GET /api/camera` SHALL store a status change with the current time and source `poll` before answering, so the history stays correct even if a webhook is missed.

#### Scenario: First read records the status
- **WHEN** no status change is recorded and Ring reports `online: true`
- **THEN** one status change `{online: true, source: "poll"}` at the current time is stored and is the newest `history` entry

#### Scenario: Unchanged status is not recorded again
- **WHEN** the latest recorded change is `online: true` and Ring reports `online: true`
- **THEN** no status change is stored

#### Scenario: Missed webhook is caught up
- **WHEN** the latest recorded change is `online: false` and Ring reports `online: true`
- **THEN** a status change `{online: true, source: "poll"}` is stored

### Requirement: Online history and uptime
`history` SHALL list the device's status changes from the last 30 days, newest first, each as `{online, at, source}` with `at` in ISO 8601. `uptime` SHALL be `{window_days: 30, percent, since}`: the share of time online from the start of the window (or from the first recorded change, if later) until now, rounded to one decimal, with `since` the start used. The status before the window counts from the window start.

#### Scenario: Uptime over the window
- **WHEN** now is 2026-10-16T12:00Z and the recorded changes are offline at 2026-10-16T00:00Z and online at 2026-10-16T06:00Z, with an online change recorded on 2026-09-01
- **THEN** `uptime.percent` is 99.2 (6 h offline in 30 days), `uptime.since` is 2026-09-16T12:00Z, and `history` lists the two October changes but not the September one

#### Scenario: Short history
- **WHEN** the only recorded changes are online at 2026-10-16T00:00Z and offline at 2026-10-16T09:00Z, and now is 2026-10-16T12:00Z
- **THEN** `uptime.percent` is 75.0 and `uptime.since` is 2026-10-16T00:00Z

#### Scenario: No history
- **WHEN** no status change is recorded and Ring is unreachable
- **THEN** `history` is `[]` and `uptime.percent` and `uptime.since` are `null`

#### Scenario: Other devices and accounts kept apart
- **WHEN** another device or another account has status changes
- **THEN** they do not appear in this camera's `history` or `uptime`

### Requirement: Camera tab
The Config "Camera" tab SHALL show the camera's product image and name, an "Online" or "Offline" badge (or "Unknown" when `online` is null), the manufacturer, video codecs, aspect ratio, max and supported resolutions (as "1080p"), image enhancements with On/Off, motion detection, end-to-end encryption and location. Values Ring did not report SHALL show as "Not reported". The camera details SHALL be read-only for every role. The tab also holds the "Blur faces" switch (see `face-blur-setting`), which only the owner sees.

#### Scenario: Camera tab shows details
- **WHEN** `GET /api/camera` answers with the details from the fixture
- **THEN** the tab shows "Fridge Cam", an "Online" badge, "Ring", "AVC", "16:9", "1080p", "HDR" with "On", "Motion detection" with "On" and "End-to-end encryption" with "Off"

#### Scenario: Camera offline
- **WHEN** `GET /api/camera` answers `online: false`
- **THEN** the badge reads "Offline"

#### Scenario: Ring unreachable
- **WHEN** `GET /api/camera` answers `ring: "unavailable"`
- **THEN** the badge reads "Unknown", the tab says "Could not reach the camera service. Showing saved details.", and the video fields show "Not reported"

#### Scenario: No camera linked
- **WHEN** `GET /api/camera` answers 409 `{"error": "no camera linked"}`
- **THEN** the tab shows "No camera is linked yet." and no "Something went wrong" notice

#### Scenario: Only the two switches are editable
- **WHEN** the owner opens the Camera tab
- **THEN** the "FridgeSense" and "Blur faces" switches are the only enabled controls that change data

### Requirement: Online history on the Camera tab
The Camera tab SHALL show the uptime as "<percent>% online" over the last 30 days, a bar of the window with online and offline spans in different colors, and the list of changes newest first, each with "Online" or "Offline" and its local date and time. With no history it SHALL show "No status changes recorded yet."

#### Scenario: History listed
- **WHEN** `history` has an offline change at 2026-10-16T00:00Z and an online change at 2026-10-16T06:00Z and `uptime.percent` is 99.2
- **THEN** the tab shows "99.2% online", two list entries with "Online" first, and a bar with one offline span

#### Scenario: Empty history
- **WHEN** `history` is `[]`
- **THEN** the tab shows "No status changes recorded yet."

### Requirement: Browser decoder readout
For the owner only, the Camera tab SHALL have a "Decoder" card with a "Check decoder" button that opens the Livestream dialog; users and viewers SHALL NOT see the card, because they can't open a live view. While video plays, the app SHALL read the browser's WebRTC inbound video stats about once a second and, after the dialog closes, show the last values: codec (e.g. "video/H264"), decoder implementation, frame size (e.g. "1920 × 1080") and frames per second. Before a check it SHALL show "Run a check to see how this browser decodes the camera's video."

#### Scenario: Decoder values after a check
- **WHEN** the owner taps "Check decoder", the stats report codec `video/H264`, decoder implementation `ExternalDecoder`, 1920 × 1080 at 15 fps, and the owner closes the dialog
- **THEN** the Decoder card shows "video/H264", "ExternalDecoder", "1920 × 1080" and "15 fps"

#### Scenario: Before any check
- **WHEN** the Camera tab opens for the owner
- **THEN** the Decoder card shows "Run a check to see how this browser decodes the camera's video." and a "Check decoder" button

#### Scenario: No video played
- **WHEN** the live view fails before any video arrives and the owner closes the dialog
- **THEN** the Decoder card still shows the "Run a check…" text

#### Scenario: No Decoder card for a viewer
- **WHEN** the Camera tab is shown to a viewer
- **THEN** no "Decoder" card and no "Check decoder" button are shown

#### Scenario: No Decoder card for a user
- **WHEN** the Camera tab is shown to a user
- **THEN** no "Decoder" card and no "Check decoder" button are shown
