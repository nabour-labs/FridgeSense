# Spec Delta

## MODIFIED Requirements

### Requirement: Door trace for every motion
When `DEBUG_TRACES` is not `false`, the fetch-stills step SHALL write a door trace for every motion it handles, whatever the outcome (`door_open`, `not_door`, `no_media`, `duplicate`). Files go under `accounts/<account_id>/devices/<device_id>/events/<start_ms>/debug/`: one `raw-<n>.jpg` per downloaded still, and `door.json`.

While face blurring is on (the default, see `face-blur-setting`), `raw-<n>.jpg` SHALL be a thumbnail: a JPEG whose longest side is at most 160 px, aspect kept and never upscaled, with a Gaussian blur applied after downscaling so faces in it cannot be recognized. The downloaded bytes SHALL NOT be stored. A still that cannot be decoded SHALL have no `raw-<n>.jpg` and `key = null`, and the rest of the trace is still written.

While face blurring is off, `raw-<n>.jpg` SHALL be the downloaded bytes.

#### Scenario: Motion that is not the door
- **WHEN** 4 stills are downloaded for window start `1786715596000` and every zone stays below its threshold
- **THEN** `raw-1.jpg` … `raw-4.jpg` and `door.json` exist under `accounts/A1/devices/D1/events/1786715596000/debug/`, `door.json` has `outcome = "not_door"`, and no door event is saved

#### Scenario: Door opening
- **WHEN** a motion is a door opening and its picked stills are stored
- **THEN** `door.json` has `outcome = "door_open"`, the `door_sk`, `opened_at`, `closed_at`, `picked` (still numbers) and `stored_keys` equal to the door event's `still_keys`

#### Scenario: Raw stills are small blurred thumbnails
- **WHEN** face blurring is on, and a 1920×1080 still is downloaded, contains a face and passes the door check
- **THEN** `raw-<n>.jpg` is a 160×90 JPEG that differs from a plain 160×90 downscale of the still (it is blurred), no trace object equals the downloaded bytes, and the `still-<k>.jpg` sent to analysis is still the full-size cropped, blurred still

#### Scenario: Portrait still
- **WHEN** face blurring is on and a downloaded still is 1080×1920
- **THEN** `raw-<n>.jpg` is 90×160

#### Scenario: Small still not upscaled
- **WHEN** face blurring is on and a downloaded still is 100×50
- **THEN** `raw-<n>.jpg` is 100×50 and blurred

#### Scenario: Still that cannot be decoded
- **WHEN** face blurring is on and still 3 of 4 downloads as bytes that are not an image
- **THEN** no `raw-3.jpg` is written, still 3 has `key = null` in `door.json`, and `raw-1.jpg`, `raw-2.jpg`, `raw-4.jpg` and `door.json` are written

#### Scenario: Raw stills are the downloaded bytes
- **WHEN** face blurring is off and a still is downloaded
- **THEN** `raw-<n>.jpg` is byte for byte the downloaded still

#### Scenario: Too few stills
- **WHEN** only 1 of 4 stills downloads and Ring answered 403 for the other three
- **THEN** `door.json` has `outcome = "no_media"`, still 1 has a `key`, and stills 2–4 have `key = null` and `missing_status = 403`

#### Scenario: Duplicate run
- **WHEN** a second run for the same Ring event ends with `duplicate`
- **THEN** its trace is written with `outcome = "duplicate"` and replaces the earlier trace's summary item for that motion

### Requirement: Tracing can be turned off
When `DEBUG_TRACES` is `false`, the pipeline SHALL write no `debug/` objects and no `TRACE#` items, and SHALL behave exactly as it does without this capability. The deployed stack SHALL set `DEBUG_TRACES=false` unless the deploy passes the CDK context `debugTraces=true`.

#### Scenario: Off
- **WHEN** `DEBUG_TRACES=false` and a door opening is analyzed
- **THEN** no object exists under the event's `debug/` prefix and no `TRACE#` item exists

#### Scenario: Off by default when deployed
- **WHEN** the stack is synthesized with no `debugTraces` context
- **THEN** the pipeline Lambda's `DEBUG_TRACES` environment variable is `false`

#### Scenario: Turned on for tuning
- **WHEN** the stack is synthesized with `-c debugTraces=true`
- **THEN** the pipeline Lambda's `DEBUG_TRACES` environment variable is `true`
