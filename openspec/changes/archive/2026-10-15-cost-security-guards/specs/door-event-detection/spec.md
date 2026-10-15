## MODIFIED Requirements

### Requirement: Stills across the opening
The system SHALL request 4 JPEG stills at evenly spaced times inside the window (at 1/5, 2/5, 3/5 and 4/5 of it) with `POST /v1/devices/{device_id}/media/image/download` and `{"type": "at_timestamp", "timestamp": <ms>, "image_options": {"format": "jpeg"}}`, follow the redirect without the `Authorization` header, and keep the downloaded bytes in memory for the door check. For a door opening only, it SHALL blur any faces in each still and store only the blurred still in S3 at `accounts/<account_id>/devices/<device_id>/events/<start_ms>/still-<n>.jpg`.

#### Scenario: Four stills saved
- **WHEN** the window is 1786715596000–1786715621000, Ring answers each request with 303 and a `Location`, the download returns JPEG bytes whose door box is bright, and face detection finds no faces
- **THEN** requests are made for timestamps 1786715601000, 1786715606000, 1786715611000 and 1786715616000, and four objects `still-1.jpg` … `still-4.jpg` exist under `accounts/ava1.ring.account.A1/devices/ava1.ring.device.D1/events/1786715596000/`

#### Scenario: Download link gets no token
- **WHEN** a still is fetched from the `Location` URL
- **THEN** that request carries no `Authorization` header

#### Scenario: Still not ready yet
- **WHEN** Ring answers 425 `RECORDING_NOT_READY` or 416 `MEDIA_NOT_FOUND` for a still
- **THEN** that still is requested again, up to 3 attempts in total

#### Scenario: Too few stills
- **WHEN** fewer than 2 of the 4 stills can be downloaded (including Ring's 403 for an unauthorized time range)
- **THEN** no face detection, no S3 write and no analysis happens, and the door event is saved with `status = "no_media"` and `still_keys = []`

#### Scenario: Too few stills survive face detection
- **WHEN** 4 bright stills are downloaded but face detection fails for 3 of them
- **THEN** no analysis happens, and the door event is saved with `status = "no_media"` and the one stored still's key in `still_keys`

#### Scenario: Stills deleted after 7 days
- **WHEN** a still has been stored for 7 days
- **THEN** the bucket's lifecycle rule deletes it

### Requirement: Door-open check before any analysis
The system SHALL compute the mean brightness (0–1) of a configured box (fractions `x, y, width, height` of the image) in each downloaded still, and SHALL treat the event as a door opening only if the brightest still reaches the configured threshold. The check SHALL run before any face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** one still's box has mean brightness 0.8 and the threshold is 0.5
- **THEN** the event counts as a door opening and goes on to analysis

#### Scenario: Door stayed closed
- **WHEN** every still's box is below the threshold
- **THEN** no analysis happens, nothing is written to the inventory, no door event is saved, and a `motion_not_door` log line records the brightest value

#### Scenario: Closed door costs no face detection
- **WHEN** 4 stills are downloaded and every still's box is below the threshold
- **THEN** face detection is never called and no object is written under the event's S3 prefix

#### Scenario: Box and threshold from config
- **WHEN** the box is configured as `0.6,0.0,0.4,1.0` and only the right 40% of a still is bright
- **THEN** that still counts as bright, while with the box `0.0,0.0,0.4,1.0` it does not

## ADDED Requirements

### Requirement: Only blurred stills are analyzed
The item analysis SHALL use only the stored (blurred) stills. No unblurred still SHALL be sent to the analysis model or stored. The door check reads the downloaded stills in memory only.

#### Scenario: Analysis receives blurred bytes
- **WHEN** a door opening's still 1 had a face blurred and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes

#### Scenario: Door check runs on downloaded stills
- **WHEN** a downloaded still's door box is bright (mean 0.8, threshold 0.5) and contains a face
- **THEN** the event counts as a door opening, face detection is called only after the door check, and only the blurred still is stored

## REMOVED Requirements

### Requirement: Only blurred stills are checked and analyzed
**Reason**: The door check now runs on the downloaded stills in memory, before face detection, so motion that is not a door opening costs no face detection or storage.
**Migration**: Replaced by "Only blurred stills are analyzed" (analysis and storage stay blurred-only) and the updated "Door-open check before any analysis".
