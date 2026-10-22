# Spec Delta

## ADDED Requirements

### Requirement: Door check follows the camera
Before scoring an event's frames or stills, the door check SHALL align them with the device's closed anchor and use the resulting rules, as set out in `door-self-calibration`. After the event is claimed, or found not to be a door opening, it SHALL store the event's sample and re-tune. A failure in alignment, sampling or re-tuning SHALL be logged and SHALL NOT change the event's outcome. The event's debug trace SHALL record the shift, the alignment error, and whether tuned rules were used.

#### Scenario: Shifted camera still detects the opening
- **WHEN** setup was run on frames where the door zone is at `x = 0.38`, and the event clip is the same scene shifted 6 px right at 128×72 with the door opening in frames 4–8
- **THEN** alignment succeeds with `dx ≈ 0.047`, the shifted zone scores frames 4–8 as open, and the outcome is `door_open`

#### Scenario: Same clip without alignment misses it
- **WHEN** the same shifted clip is checked with alignment turned off (no anchor stored)
- **THEN** the outcome is `not_door`

#### Scenario: Alignment error does not drop an opening
- **WHEN** reading the alignment from the table raises an error
- **THEN** the event is checked with the unshifted rules, a `door_alignment_unavailable` warning is logged, and the outcome is decided as before

#### Scenario: Re-tune failure after a claimed opening
- **WHEN** the door event is claimed and storing the sample raises an error
- **THEN** the outcome is still `door_open` and a `door_sample_failed` warning is logged

#### Scenario: Trace records the shift
- **WHEN** an event aligns with shift `(0.016, 0)`, error 0.031, and tuned rules are in use
- **THEN** the door trace has `alignment = {"dx": 0.016, "dy": 0, "error": 0.031, "ok": true}` and `rules = "tuned"`
