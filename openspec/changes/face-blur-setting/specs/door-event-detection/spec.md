# Spec Delta

## MODIFIED Requirements

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
