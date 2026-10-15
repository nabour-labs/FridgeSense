# Spec Delta

## MODIFIED Requirements

### Requirement: Stills across the opening
The system SHALL request 4 JPEG stills at evenly spaced times inside the window (at 1/5, 2/5, 3/5 and 4/5 of it) with `POST /v1/devices/{device_id}/media/image/download` and `{"type": "at_timestamp", "timestamp": <ms>, "image_options": {"format": "jpeg"}}`, follow the redirect without the `Authorization` header, blur any faces in each still, and store only the blurred still in S3 at `accounts/<account_id>/devices/<device_id>/events/<start_ms>/still-<n>.jpg`.

#### Scenario: Four stills saved
- **WHEN** the window is 1786715596000–1786715621000 and Ring answers each request with 303 and a `Location`, the download returns JPEG bytes, and face detection finds no faces
- **THEN** requests are made for timestamps 1786715601000, 1786715606000, 1786715611000 and 1786715616000, and four objects `still-1.jpg` … `still-4.jpg` exist under `accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/`

#### Scenario: Download link gets no token
- **WHEN** a still is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Still not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND` for a still
- **THEN** that still is requested again, up to 3 attempts in total

#### Scenario: Too few stills
- **WHEN** fewer than 2 of the 4 stills can be downloaded and blurred (including Ring's 403 for an unauthorized time range, or face detection failing)
- **THEN** no analysis happens, and the door event is saved with `status = "no_media"`

#### Scenario: Stills deleted after 7 days
- **WHEN** a still has been stored for 7 days
- **THEN** the bucket's lifecycle rule deletes it

## ADDED Requirements

### Requirement: Faces blurred before storage
Before a still is stored, the system SHALL send its downloaded bytes to face detection and SHALL blur every face reported, whatever its confidence. Each face box (fractions of the image) SHALL be enlarged by 30% about its centre, clipped to the image, and made unrecognizable. A still with no faces SHALL be stored byte for byte as downloaded.

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
- **WHEN** face detection reports no faces for a still
- **THEN** the stored object's bytes are identical to the downloaded bytes

#### Scenario: Detection sees the downloaded bytes, S3 sees only the result
- **WHEN** a still is downloaded and face detection reports one face
- **THEN** the detection request carries the downloaded JPEG bytes inline (not an S3 reference), and the only object written for that still is the blurred JPEG with `ContentType = "image/jpeg"`

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

### Requirement: Only blurred stills are checked and analyzed
The door-open check and the item analysis SHALL use only the stored (blurred) stills. No unblurred still SHALL be sent to the analysis model.

#### Scenario: Analysis receives blurred bytes
- **WHEN** a door opening's still 1 had a face blurred and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes

#### Scenario: Door check runs on blurred stills
- **WHEN** a still's door box is bright (mean 0.8, threshold 0.5) and a face inside the door box is blurred
- **THEN** the door check is computed from the blurred still and the event still counts as a door opening

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
