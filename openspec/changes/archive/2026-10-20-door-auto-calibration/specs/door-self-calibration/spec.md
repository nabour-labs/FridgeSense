# Spec Delta

## Purpose

Keeps the owner's open/close setup accurate as the camera shifts and the scene changes: zones follow small camera moves, larger moves are detected and reported, and the door rules are re-tuned from recent events.

## ADDED Requirements

### Requirement: Closed anchor stored when setup runs
A successful `POST /api/door-calibration/run` SHALL also store the device's *closed anchor*: the newest closed reference's whole image, converted to grayscale, scaled to 128×72 and turned into an edge map. It SHALL reset the device's alignment to a shift of `(0, 0)` with no failures and not moved, keeping `last_moved_at`. A failed run SHALL leave the anchor and alignment unchanged.

#### Scenario: Anchor from the newest closed reference
- **WHEN** setup runs on two closed references (older A, newer B) and one open reference
- **THEN** the stored anchor is B's edge map at 128×72, and the alignment reads `{"dx": 0, "dy": 0, "failures": 0, "moved": false}`

#### Scenario: Failed run keeps the anchor
- **WHEN** an anchor and a shift of `(0.02, 0)` are stored and a new run fails with 422
- **THEN** the stored anchor and the shift `(0.02, 0)` are unchanged

### Requirement: Event alignment against the anchor
For each motion event with at least 2 frames and an anchor, the first and last frames SHALL each be compared with the anchor over every whole-pixel shift from −8 to +8 on both axes at 128×72. The *error* of a shift is the mean absolute difference of the overlapping edge pixels divided by 255. The bookend with the lower best error is used. If that error is at most `ALIGN_MAX_ERROR` (default 0.05), alignment *succeeds*, and the shift becomes `dx = px / 128` and `dy = py / 72`.

#### Scenario: Known shift found
- **WHEN** the anchor is a test pattern and the event's first frame is the same pattern shifted 5 px right and 2 px down at 128×72
- **THEN** alignment succeeds with `dx = 0.039` and `dy = 0.028` (±0.001) and an error below 0.02

#### Scenario: Better bookend used
- **WHEN** the first frame has a person covering half the view and the last frame is the anchor shifted 3 px left
- **THEN** the last frame is used and the shift is `dx = −0.023`, `dy = 0`

#### Scenario: Alignment fails
- **WHEN** both bookends are the anchor rotated 15°, so the best error is above 0.05
- **THEN** alignment fails, and the event's door check uses the last stored shift

#### Scenario: Lighting change alone
- **WHEN** the first frame is the anchor's source image at 60% brightness, unshifted
- **THEN** alignment succeeds with shift `(0, 0)`

#### Scenario: No anchor
- **WHEN** setup never ran, or the event has fewer than 2 frames
- **THEN** no alignment is attempted and the stored alignment is unchanged

### Requirement: Alignment state stored per device
After each attempted alignment, the device's alignment SHALL be stored: on success, the new `dx`, `dy` and `error`, with `failures` set to 0; on failure, `failures` increased by 1 and the shift unchanged. `checked_at` SHALL be the event's start time.

#### Scenario: Success resets failures
- **WHEN** `failures` is 2 and the next event aligns with shift `(0.01, 0)`
- **THEN** the stored alignment has `dx = 0.01`, `dy = 0`, `failures = 0`

#### Scenario: Failure counts up
- **WHEN** `failures` is 1 and the next event fails to align
- **THEN** `failures` is 2 and `dx`, `dy` are unchanged

### Requirement: Camera moved detection
The camera SHALL count as moved when `failures` reaches 3, or when a successful shift has `|dx| ≥ 0.04` or `|dy| ≥ 0.04`. `moved_at` and `last_moved_at` SHALL be set to the event start that first caused it and SHALL NOT change while the camera stays moved. Only a successful setup run SHALL clear `moved` and `moved_at`; `last_moved_at` is kept.

#### Scenario: Three failed alignments
- **WHEN** three events in a row fail to align
- **THEN** the alignment reads `moved = true` with `moved_at` the third event's start time

#### Scenario: Large shift
- **WHEN** an event aligns with `dx = 0.047`
- **THEN** the alignment reads `moved = true`, and that event's door check still uses the shifted zones

#### Scenario: Stays moved after a good event
- **WHEN** the camera is moved and the next event aligns with shift `(0, 0)`
- **THEN** `moved` stays true and `moved_at` is unchanged

#### Scenario: Setup run clears moved
- **WHEN** the camera is moved and the owner runs setup successfully
- **THEN** the alignment reads `moved = false`, `moved_at = null`, `failures = 0`, shift `(0, 0)`, and `last_moved_at` is still the time it moved

### Requirement: Event samples from recent activity
For each aligned event, a sample SHALL be stored per setup zone, measured with the shifted zone boxes. The *closed sample* is the bookend used for alignment, kept only if the current rules call that zone closed in it. The *open sample* is the frame whose `change` from the closed sample is highest in that zone, kept only if that change is at least 0.08 and the closed sample was kept. Each sample holds the zone's `color`, `blue` and `brightness` values and its 32×32 RGB thumbnail. The newest 20 sample events per device SHALL be kept and older ones deleted.

#### Scenario: Opening sampled
- **WHEN** an aligned event's last frame is closed in zone 1, and frame 6 is the lit interior with `change = 0.30` from it
- **THEN** a sample is stored for zone 1 with the last frame as closed and frame 6 as open

#### Scenario: Missed opening still sampled
- **WHEN** the current rules found no opening (outcome `not_door`), but one frame's `change` from the closed bookend is 0.25 in zone 1
- **THEN** a sample is stored with that frame as zone 1's open sample

#### Scenario: No clear opening
- **WHEN** no frame's `change` from the closed bookend reaches 0.08 in a zone
- **THEN** that zone's sample has a closed value and `open = null`

#### Scenario: Bookend not closed
- **WHEN** the current rules call zone 1 open in the alignment bookend
- **THEN** zone 1's sample has `closed = null` and `open = null`, since an opening can't be measured against a bookend that isn't closed

#### Scenario: Oldest dropped
- **WHEN** 20 sample events are stored and a 21st is added
- **THEN** 20 remain and the oldest is gone

#### Scenario: Unaligned event not sampled
- **WHEN** alignment fails or there is no anchor
- **THEN** no sample is stored

### Requirement: Rules re-tuned from samples
After a sample is stored, setup's rule choice (features, direction, threshold, margin, baseline) SHALL be re-run per zone on the owner's references (at their own boxes) plus the stored samples (as measured). This needs at least 3 open and 3 closed samples per zone. The result SHALL be stored as the tuned rules only if every zone separates with a margin of at least 0.01. Otherwise the current rules stay. The baseline is the mean thumbnail of all closed references and closed samples.

#### Scenario: Tuned rules adopted
- **WHEN** zone 1 has 2 owner references and 4 open and 4 closed samples whose `color` values separate with a margin of 0.06
- **THEN** tuned rules are stored for zone 1 with feature `color`, `tuned_at` set, and `tuned_from = 8`

#### Scenario: Samples overlap
- **WHEN** one open sample's values all fall inside the closed samples' range for every feature
- **THEN** no tuned rules are stored, and the previous rules (tuned or owner) stay in use

#### Scenario: Too few samples
- **WHEN** zone 2 has only 2 open samples
- **THEN** no re-tune runs

### Requirement: Rules the door check uses
The door check SHALL use the device's tuned rules if any, else the owner's setup rules, with every zone box moved by the stored shift (`x + dx`, `y + dy`) and clamped inside the image. A successful setup run SHALL delete the tuned rules and all samples.

#### Scenario: Shifted zones
- **WHEN** a setup zone is `{"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}` and the shift is `(0.03, −0.02)`
- **THEN** the door check scores the box `{"x": 0.41, "y": 0.30, "width": 0.21, "height": 0.30}`

#### Scenario: Clamped at the edge
- **WHEN** a zone has `x = 0.85`, `width = 0.12` and the shift is `dx = 0.05`
- **THEN** the scored box has `x = 0.88`, `width = 0.12`

#### Scenario: Re-running setup resets tuning
- **WHEN** tuned rules and 12 samples exist and the owner runs setup successfully
- **THEN** the door check uses the new owner rules, and no samples remain

### Requirement: Door setup reports alignment and tuning
The `GET /api/door-calibration` body SHALL include `"alignment": {"dx", "dy", "error", "failures", "moved", "moved_at", "last_moved_at", "checked_at"} | null` (null when setup never ran), with values rounded to 3 places. Its `setup` SHALL include `"tuned_at": "<ISO 8601 UTC>" | null` and `"tuned_from": <sample count> | null`.

#### Scenario: Reported after an aligned event
- **WHEN** setup ran and one event aligned with shift `(0.016, 0)`
- **THEN** the body has `alignment.dx = 0.016`, `alignment.moved = false`, and `setup.tuned_at = null`

#### Scenario: Before any event
- **WHEN** setup ran and no event has happened since
- **THEN** `alignment` is `{"dx": 0, "dy": 0, "error": null, "failures": 0, "moved": false, "moved_at": null, "last_moved_at": null, "checked_at": null}`
