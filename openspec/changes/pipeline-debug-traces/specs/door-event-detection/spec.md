# Spec Delta

## MODIFIED Requirements

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
