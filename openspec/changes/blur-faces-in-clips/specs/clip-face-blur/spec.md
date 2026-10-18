# Spec Delta

## Purpose

Blurs every face in a door opening's open-span clip before the clip can be played, while leaving everything outside the faces as recorded. If blurring can't be done, the clip is dropped rather than shown unblurred.

## ADDED Requirements

### Requirement: Faces found in every frame
For a raw clip, the system SHALL run face detection on every decoded frame, using the `deface` CenterFace model with a score threshold of 0.2. Detection MAY run on a copy of the frame scaled to at most 1280 px wide, with face boxes mapped back to full size.

#### Scenario: Face in some frames
- **WHEN** a 30-frame raw clip has a face reported by the detector in frames 10–19 only
- **THEN** detection ran on all 30 frames, and frames 10–19 are blurred in the output while frames 0–9 and 20–29 have no blurred area

#### Scenario: Low score ignored
- **WHEN** the detector reports a box with score 0.15 on a frame
- **THEN** that box is not blurred

### Requirement: Only face areas blurred
For each detected face, the system SHALL blur an ellipse inscribed in the face box enlarged by 30% about its centre and clipped to the frame, so that the face can't be recognized. Pixels outside every enlarged box SHALL NOT be changed beyond re-encoding: on a frame's luminance, their mean absolute difference from the raw frame SHALL be at most 3 (of 255).

#### Scenario: One face blurred
- **WHEN** a 640×360 raw clip shows a black-and-white checkerboard of 8 px squares, and the detector reports one face box `(x1=256, y1=72, x2=384, y2=216)` with score 0.9 in every frame
- **THEN** in every output frame the luminance standard deviation inside the ellipse of the enlarged box `(237, 50, 403, 238)` is below 10, and outside that box the mean absolute luminance difference from the raw frame is at most 3

#### Scenario: Two faces blurred
- **WHEN** the detector reports two face boxes on the checkerboard clip, `(32, 36, 128, 144)` and `(448, 108, 544, 216)`
- **THEN** both enlarged ellipses have luminance standard deviation below 10, and the area between them is unchanged within the tolerance

#### Scenario: Face at the frame edge
- **WHEN** a face box is `(600, 300, 660, 380)` on a 640×360 frame
- **THEN** the enlarged box is clipped to the frame, and blurring raises no error

#### Scenario: No faces
- **WHEN** the detector reports no faces in any frame
- **THEN** every output frame's mean absolute luminance difference from the raw frame is at most 3

### Requirement: Playable output with the same timing
The blurred clip SHALL be H.264 video in `yuv420p` in an MP4 with `+faststart`, with no audio track. It SHALL have the same frame size, frame count and frame rate as the raw clip, so the door event's `clip_span` still marks the open span.

#### Scenario: Same timing
- **WHEN** a 1920×1080 raw clip of 120 frames at 15 fps is blurred
- **THEN** the output is 1920×1080, has 120 frames at 15 fps, its codec is `h264`, its pixel format is `yuv420p`, and it has no audio stream

### Requirement: Blurred clip published
After blurring, the system SHALL store the output as `clip.mp4` under the event's stills prefix, then set `clip_key`, `clip_span` (from the input) and `clip_blurred = true` on the door event, then delete `clip-raw.mp4`. The door event update SHALL only succeed if the event still exists. It SHALL log `clip_blurred` with `device_id`, `frames`, `frames_with_faces` and `duration_ms`.

#### Scenario: Clip published
- **WHEN** the blur step gets `{"raw_key": ".../clip-raw.mp4", "clip_span": [0.5, 8.5], "door_sk": "DOOR#…"}` for an existing door event, and blurring succeeds
- **THEN** `.../clip.mp4` exists, the door event has `clip_key = ".../clip.mp4"`, `clip_span = [0.5, 8.5]` and `clip_blurred = true`, `.../clip-raw.mp4` no longer exists, and `clip_blurred` is logged

#### Scenario: Event deleted while blurring
- **WHEN** the owner deleted the door event before the blur step updates it
- **THEN** no door event is recreated, and both `clip.mp4` and `clip-raw.mp4` are deleted

### Requirement: Fail closed
If the raw clip can't be read, decoded, blurred, encoded or stored, or the step times out, the system SHALL NOT set `clip_key` on the door event and SHALL delete `clip-raw.mp4` and any partial `clip.mp4`. It SHALL log `clip_not_stored` with `reason = "blur_failed"`. The door event's status, changes and stills SHALL be unaffected, and the workflow run SHALL still succeed.

#### Scenario: Decode error
- **WHEN** `clip-raw.mp4` is not a valid video
- **THEN** the door event has no `clip_key`, `clip-raw.mp4` is deleted, `clip_not_stored` is logged with `reason = "blur_failed"`, and the run ends in `Done`

#### Scenario: Detector fails
- **WHEN** the detector raises an error on frame 5
- **THEN** no `clip.mp4` is written, and the door event has no `clip_key`

#### Scenario: Blur step times out
- **WHEN** the blur Lambda times out
- **THEN** the workflow's catch deletes `clip-raw.mp4`, logs `clip_not_stored` with `reason = "blur_failed"`, and the run ends in `Done` with the event's analysis kept

### Requirement: Raw clips expire
`clip-raw.mp4` objects SHALL be tagged `transient=true`, and the stills bucket SHALL have a lifecycle rule that expires objects with that tag after 1 day.

#### Scenario: Lifecycle rule synthesized
- **WHEN** the stack is synthesized
- **THEN** the stills bucket has a lifecycle rule with tag filter `transient=true` and expiration 1 day, alongside the existing 7-day rule

#### Scenario: Raw clip tagged
- **WHEN** the pipeline stores `clip-raw.mp4`
- **THEN** the object has the tag `transient=true`

### Requirement: Clip blur cost logged
Each blur run SHALL log `clip_blur_cost` with `device_id`, `billed_ms`, `memory_mb` and `usd` = `billed_ms / 1000 × memory_mb / 1024 × 0.0000133334`, rounded to 6 decimals.

#### Scenario: Cost logged
- **WHEN** a blur run takes 30,000 ms with 3008 MB
- **THEN** `clip_blur_cost` is logged with `usd = 0.001175`
