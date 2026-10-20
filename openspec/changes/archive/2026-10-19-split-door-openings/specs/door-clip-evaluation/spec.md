## MODIFIED Requirements

### Requirement: Per-clip door check test
For each labelled clip found in the clips folder, a test marked `clips` SHALL run the unchanged fetch-stills task on that clip with the configured door check (`DOOR_ZONES`, `DOOR_THRESHOLD`, `STILL_INTERVAL_MS`, or their defaults). It SHALL check the outcome and the event's open and close times against the labels. The tolerance is 1.5 × the still spacing: the still interval, or the wider spacing the pipeline uses when a long window hits its 30-still cap. With several openings in one clip, the test SHALL check the first door event. Its expected span runs from the first `opened_s` to the `closed_s` of the last opening before the first gap of 10 s or more between one opening's `closed_s` and the next one's `opened_s`. A `null` close means the window end.

#### Scenario: Opening found with correct times
- **WHEN** a clip is labelled `[{"opened_s": 4.0, "closed_s": 12.5}]`, the still interval is 1000 ms, and the door event's `opened_at` is window start + 4.6 s and `closed_at` is window start + 13.0 s
- **THEN** the test passes

#### Scenario: Openings separated by a long gap
- **WHEN** a clip is labelled `[{"opened_s": 0.0, "closed_s": 38.0}, {"opened_s": 111.0, "closed_s": null}]`
- **THEN** the expected span is 0.0–38.0 s

#### Scenario: Open time too far off
- **WHEN** the same clip's door event has `opened_at` = window start + 6.0 s
- **THEN** the test fails, and the message names the clip, the labelled and detected open times, and the 1.5 s tolerance

#### Scenario: Missed opening
- **WHEN** a clip is labelled with one opening and the task ends with `not_door`
- **THEN** the test fails with a message naming the clip and "missed opening", along with the best zone value and the threshold

#### Scenario: False opening
- **WHEN** a clip is labelled `[]` and the task ends with `door_open`
- **THEN** the test fails with a message naming the clip and "false opening", along with the detected open and close times

#### Scenario: No opening, none detected
- **WHEN** a clip is labelled `[]` and the task ends with `not_door`
- **THEN** the test passes

#### Scenario: Door still open at clip end
- **WHEN** a clip is labelled `[{"opened_s": 3.0, "closed_s": null}]` and the door event's `closed_at` is the window end
- **THEN** the close time counts as correct

#### Scenario: Two openings in one clip
- **WHEN** a clip is labelled `[{"opened_s": 2.0, "closed_s": 6.0}, {"opened_s": 15.0, "closed_s": 20.0}]`
- **THEN** the gap is 9 s, so the expected open time is window start + 2.0 s and the expected close time is window start + 20.0 s

#### Scenario: Shorter still interval
- **WHEN** `STILL_INTERVAL_MS=500` is set
- **THEN** stills are requested about every 500 ms and the tolerance is 0.75 s

#### Scenario: Long clip hits the still cap
- **WHEN** a clip lasts 120.0 s and the still interval is 1000 ms
- **THEN** 30 stills are requested about 3.9 s apart and the tolerance is 1.5 × that spacing (about 5.8 s)
