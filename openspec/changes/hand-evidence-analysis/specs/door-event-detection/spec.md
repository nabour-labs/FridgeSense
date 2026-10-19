## RENAMED Requirements

- FROM: `### Requirement: Only blurred stills are analyzed`
- TO: `### Requirement: Only blurred media is shown`

## MODIFIED Requirements

### Requirement: Only blurred media is shown
While face blurring is on, every image or clip that a door event links or an API returns SHALL be blurred, including each change's proof images. The analysis model MAY receive unblurred frames, but only through the transient analysis video. The analysis video SHALL never be linked on a door event, returned or signed by any API, or listed in a trace with a `key`. The analyze step SHALL delete it after the analysis, whether it succeeded or failed. Without an analysis video, the analysis uses only the stored stills. The door check reads the downloaded, uncropped frames in memory.

#### Scenario: Analysis receives blurred bytes
- **WHEN** face blurring is on, a door opening has no analysis video, its still 1 had a face blurred, and the event goes on to analysis
- **THEN** the image bytes for still 1 in the analysis request equal the stored blurred object, not the downloaded bytes or `debug/raw-<n>.jpg`

#### Scenario: Analysis video never shown
- **WHEN** face blurring is on and a door opening has an analysis video
- **THEN** the door event has no field holding the `analysis.mp4` key, `GET /api/events` and `GET /api/debug/motions/{id}` return no link to it, and the stored stills and `clip.mp4` are blurred as before

#### Scenario: Analysis video deleted after analysis
- **WHEN** the analyze step finishes, whether the answer was valid, invalid twice, or Bedrock rejected the request
- **THEN** `analysis.mp4` no longer exists under the event's prefix

#### Scenario: Analysis video deleted when the step is retried
- **WHEN** the analyze step raises `BedrockRetryable` and the workflow retries it
- **THEN** the video is kept for the retry, and it is deleted by the run that finishes the step or expires with the `transient=true` lifecycle rule within 1 day

#### Scenario: Door check runs on downloaded stills
- **WHEN** a downloaded still passes the door check and contains a face
- **THEN** the event counts as a door opening, face detection is called only after the door check, and the only stored event still is the blurred one

#### Scenario: No debug stills when tracing is off
- **WHEN** `DEBUG_TRACES=false` and a downloaded still contains a face
- **THEN** no unblurred copy of it is stored anywhere except the transient analysis video

### Requirement: Stills cropped to the visible area
When the device has a fridge area, the system SHALL crop each still of a door opening to the analysis crop box (see "Analysis crop from the fridge area"). Otherwise, when `STILL_CROP` is set (fractions `x, y, width, height` of the downloaded still), it SHALL crop each still to that box. The crop is re-encoded as JPEG before face detection, so the stored still and the analysis image are the crop. With neither, stills SHALL NOT be cropped. Stills of events that fail the door check SHALL never be cropped or stored.

#### Scenario: Crop to the visible strip
- **WHEN** the device has no fridge area, `STILL_CROP` is `0.30,0.0,0.34,1.0` and a door opening's still is 2560×1440
- **THEN** the image sent to face detection and the stored `still-<n>.jpg` are 870×1440 (±1 px per side), and their pixels match the downloaded still's region starting at x = 768

#### Scenario: Fridge area wins over STILL_CROP
- **WHEN** the device's fridge area is `x = 0.362, y = 0.329, width = 0.233, height = 0.611`, `STILL_CROP` is `0.30,0.0,0.34,1.0`, and a door opening's still is 2560×1440
- **THEN** the stored `still-<n>.jpg` is the analysis crop box's region, 716×968 (±2 px per side)

#### Scenario: Analysis sees the cropped still
- **WHEN** a crop applies and the event goes on to analysis with stills
- **THEN** each image in the analysis request has the cropped dimensions and equals the stored object

#### Scenario: No crop configured
- **WHEN** the device has no fridge area and `STILL_CROP` is not set
- **THEN** the stored still has the downloaded dimensions, and with no faces its bytes are identical to the downloaded bytes

#### Scenario: Door check ignores the crop
- **WHEN** `STILL_CROP` is `0.0,0.0,0.5,1.0` and the only colorful pixels are in a zone at `0.6,0.0,0.4,1.0`
- **THEN** the event still counts as a door opening, because the door check uses the uncropped still

#### Scenario: Invalid crop config
- **WHEN** `STILL_CROP` is `0.8,0,0.5,1` (past the right edge) or `0,0,1` (three numbers)
- **THEN** the fetch-stills task fails with an error naming `STILL_CROP`, before any Ring request is made

### Requirement: Clips never stored
The full event clip SHALL only be held in memory or in a temporary file in Lambda `/tmp`. The temporary file SHALL be deleted when the step ends, whether it succeeds or fails. The only clip objects written to S3 SHALL be a door opening's open-span `clip.mp4`, while face blurring is on its transient `clip-raw.mp4` (see `clip-face-blur`), and its transient `analysis.mp4` (see "Analysis video built from the open span"). Apart from those clips, the stored stills and the debug-trace frames, no frame SHALL be written to S3.

#### Scenario: Door opening processed
- **WHEN** a door opening is processed from a clip with debug traces off and face blurring off
- **THEN** the only S3 objects the fetch step writes are `still-<n>.jpg`, one `clip.mp4` and one `analysis.mp4`, `clip.mp4` is shorter than the event clip, and after the run only `still-<n>.jpg` and `clip.mp4` remain

#### Scenario: Door opening processed with blurring on
- **WHEN** a door opening is processed from a clip with debug traces off and face blurring on, and the blur step succeeds
- **THEN** after the run the only S3 objects under the event's prefix are `still-<n>.jpg` and one `clip.mp4`, and no `clip-raw.mp4` or `analysis.mp4` remains

#### Scenario: Temporary file removed on error
- **WHEN** decoding fails partway through the clip
- **THEN** the temporary clip file no longer exists after the step

#### Scenario: Temporary file removed after the cut
- **WHEN** a door opening's clip is cut and stored
- **THEN** neither the downloaded clip nor the cut leaves a file behind in the clip directory

## ADDED Requirements

### Requirement: Analysis crop from the fridge area
The analysis crop box SHALL be the device's fridge area widened by 10% of its width on each side and by 5% of its height above and below, then clamped to the frame. Without a fridge area, the analysis crop box is the `STILL_CROP` box, or the full frame when that is unset.

#### Scenario: Box from the fridge area
- **WHEN** the fridge area is `x = 0.362, y = 0.329, width = 0.233, height = 0.611`
- **THEN** the analysis crop box is `x ≈ 0.3387, y ≈ 0.2985, width ≈ 0.2796, height ≈ 0.6721` (to 4 places)

#### Scenario: Box clamped at the frame edge
- **WHEN** the fridge area is `x = 0.0, y = 0.5, width = 0.4, height = 0.5`
- **THEN** the analysis crop box is `x = 0.0, y = 0.475, width = 0.44, height = 0.525`

#### Scenario: No fridge area
- **WHEN** the device has no fridge area and `STILL_CROP` is `0.30,0.0,0.34,1.0`
- **THEN** the analysis crop box is `0.30, 0.0, 0.34, 1.0`

### Requirement: Analysis video built from the open span
For a door opening found in the event clip, the system SHALL build an H.264 MP4 from the decoded frames, starting one frame before the open span (when there is one) and running through the span. Each frame is cropped to the analysis crop box and played at 1 frame per second. Over 40 frames, it keeps every `ceil(n / 40)`-th frame. It is stored as `analysis.mp4` tagged `transient=true` under the stills prefix, unblurred whatever the face-blur setting.

#### Scenario: Short opening
- **WHEN** the frame interval is 500 ms, the open span is frames 3–12 of the clip, and the fridge area gives a 716×968 crop
- **THEN** `analysis.mp4` is stored with tag `transient=true`, decodes to 11 frames (frames 2–12) of 716×968 (±2 px), lasts 11 s, and the step output has `analysis_video = {"key": <its key>, "start_ms": <frame 2's time>, "frame_ms": 500, "frames": 11}`

#### Scenario: Long opening thinned
- **WHEN** the frame interval is 500 ms and the open span plus the frame before it is 231 frames
- **THEN** the video keeps every 6th frame, starting with the first: 39 frames with `frame_ms = 3000`

#### Scenario: Span starts at the first frame
- **WHEN** the open span starts at the clip's first frame
- **THEN** the video starts at that frame and `start_ms` is its time

#### Scenario: Built while face blurring is on
- **WHEN** face blurring is on and a frame in the span shows a face
- **THEN** the video frame is not blurred, the stored stills are blurred, and the door event links neither `analysis.mp4` nor its key

#### Scenario: Encoding or upload fails
- **WHEN** encoding the video raises an error or S3 rejects the upload
- **THEN** `analysis_video_not_stored` is logged with `reason` `encode_failed` or `upload_failed`, the step output has no `analysis_video`, the stills are stored, and the outcome is still `door_open`

#### Scenario: No video on the fallback path
- **WHEN** the clip is unavailable and the door check samples stills across the window
- **THEN** no `analysis.mp4` is written and the step output has no `analysis_video`

#### Scenario: Not a door opening
- **WHEN** the outcome is `not_door` or `duplicate`
- **THEN** no `analysis.mp4` remains under the event's prefix

### Requirement: Still times passed to analysis
For a door opening, the step output SHALL include `still_ms`: the capture time in epoch ms of each stored still, in the same order as `still_keys`.

#### Scenario: Times match the stored stills
- **WHEN** the stills picked from the open span were taken at offsets 0, 3000, 6000 and 9500 ms from the window start `S`
- **THEN** the step output has `still_ms = [S, S + 3000, S + 6000, S + 9500]` alongside the four `still_keys`

#### Scenario: Still dropped by face detection
- **WHEN** 4 stills were picked and face detection failed for the second
- **THEN** `still_keys` has 3 keys and `still_ms` has the 3 matching times
