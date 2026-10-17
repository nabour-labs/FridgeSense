## MODIFIED Requirements

### Requirement: Door-open check before any analysis
The system SHALL decide for each downloaded still whether it is *open*, using rules for zones, each a box of fractions `x, y, width, height` of the downloaded still.
- **With a setup result** stored for the event's account and device (see the `door-calibration` capability), each zone has its own feature (`blue`, `color`, `brightness` or `change`, measured as setup measures it, against the stored baseline for `change`), direction and threshold. A still is open when, in any zone, the feature's value is at or above the threshold (direction `above`) or at or below it (direction `below`).
- **Without a setup result**, every zone uses `blue` with direction `above`: the fraction of pixels that are both colorful (`max(R,G,B) − min(R,G,B) > 60` and `max(R,G,B) > 100`) and blue-lit (`B − max(R,G) > 20`), as the fridge's LED-lit interior is. Warm colors such as food held in front of the closed doors do not count. The zones are `DOOR_ZONES`, else the defaults `0.38,0.32,0.21,0.30` (doors) and `0.455,0.60,0.12,0.18` (drawers), and the threshold is `DOOR_THRESHOLD`, else 0.01.

A still's *score* is the value of its best zone, the one furthest past (or closest to) its threshold. The event SHALL count as a door opening only if at least one still is open. The *open span* runs from the first open still through the first still after the last open one (or through the last open still if no still follows it). Up to 4 stills SHALL be sent on from the open span, evenly spaced and including its first and last still: positions `round(i · (n − 1) / 3)` for `i = 0 … 3` in a span of `n > 4` stills, or every still when `n ≤ 4`. The check SHALL run on the downloaded stills before any cropping, face detection or storage. Only door openings go on to face detection, storage and analysis.

#### Scenario: Fridge light visible
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and one 200×100 still is grey `(128,128,128)` except a `(40,90,200)` block covering 10% of the left zone
- **THEN** the event counts as a door opening with `score` ≈ 0.10 from zone 1, and goes on to analysis

#### Scenario: Drawer opening seen only in the drawers zone
- **WHEN** zones are `0.0,0.0,0.5,1.0;0.5,0.0,0.5,1.0`, the threshold is 0.02, and the only blue-lit pixels are a `(40,90,200)` block covering 5% of the right zone
- **THEN** the event counts as a door opening with `score` ≈ 0.05 from zone 2

#### Scenario: Setup result used for the device
- **WHEN** setup for the event's device stored zone `0.6,0.0,0.4,1.0` with `color` above 0.3, `DOOR_ZONES` is `0.0,0.0,0.4,1.0`, and only the right 40% of a still is colorful (a color value of 1.0 in the stored zone)
- **THEN** the event counts as a door opening, and the `door_event_recorded` log line has `zones_source = "setup"`

#### Scenario: Setup threshold applied
- **WHEN** setup stored `color` above 0.3 for a zone and the best still has a color value of 0.2 there
- **THEN** the event is not a door opening, although 0.2 is above `DOOR_THRESHOLD`

#### Scenario: Brightness rule applied
- **WHEN** setup stored `brightness` above 0.6 for the whole image, and the stills are plain `(200,200,200)` in one run and plain `(100,100,100)` in another
- **THEN** the first run is a door opening and the second is not

#### Scenario: Darker rule applied
- **WHEN** setup stored `brightness` below 0.5 for the whole image and a still is plain `(90,90,90)`
- **THEN** that still is open

#### Scenario: Change rule applied
- **WHEN** setup stored `change` above 0.2 for the whole image with a plain `(128,128,128)` baseline, and a still's left half is `(40,40,40)` and right half `(216,216,216)`
- **THEN** that still is open, while a plain `(130,130,130)` still is not

#### Scenario: Fallback when setup never ran
- **WHEN** no setup result is stored for the event's device and `DOOR_ZONES` is `0.6,0.0,0.4,1.0`
- **THEN** the check uses `DOOR_ZONES` and `DOOR_THRESHOLD`, and the log line has `zones_source = "default"`

#### Scenario: Setup lookup fails
- **WHEN** reading the setup result from the table raises an error
- **THEN** the check uses the defaults, logs `door_setup_unavailable` as a warning, and the run continues

#### Scenario: Door stayed closed
- **WHEN** no still reaches the threshold in any zone
- **THEN** no analysis happens, nothing is written to the inventory, no door event is saved, and a `motion_not_door` log line records `score` (the best still's value, rounded to 3 places), `zone` (1-based), `feature`, `threshold` and `zones_source`, and the run output has `outcome = "not_door"` and `score`

#### Scenario: Brightness alone does not count
- **WHEN** every still is uniform grey `(230,230,230)` (bright stainless steel in daylight) or `(30,30,30)` (dim room)
- **THEN** the score is 0 and the event is not a door opening

#### Scenario: Dark colored clothing does not count
- **WHEN** the only non-grey pixels in a zone are navy `(20,25,60)`
- **THEN** those pixels are not colorful and the event is not a door opening

#### Scenario: Threshold is inclusive
- **WHEN** a still's best zone has a feature value exactly equal to the threshold
- **THEN** that still is open and the event counts as a door opening

#### Scenario: Closed door costs no face detection
- **WHEN** 25 stills are downloaded and no still reaches the threshold in any zone
- **THEN** face detection is never called and no object is written under the event's S3 prefix

#### Scenario: Box and threshold from config
- **WHEN** no setup result is stored for the device, `DOOR_ZONES` is `0.6,0.0,0.4,1.0`, and only the right 40% of a still is blue-lit `(40,90,200)`
- **THEN** that still counts as a door opening, while with `DOOR_ZONES = 0.0,0.0,0.4,1.0` it does not

#### Scenario: Invalid zone config
- **WHEN** no setup result is stored and `DOOR_ZONES` is `0.9,0,0.5,1` (past the right edge), `0,0,1` (three numbers) or empty after splitting on `;`
- **THEN** the fetch-stills task fails with an error naming `DOOR_ZONES`, before any Ring request is made

#### Scenario: Food in front of closed doors
- **WHEN** no setup result is stored, zones are `0.0,0.0,1.0,1.0`, and every still is grey `(128,128,128)` except a yellow `(220,170,40)` plate covering 10% of the zone, or a red `(200,40,40)` packet covering 10%
- **THEN** the score is 0, no still is open, and the event is not a door opening

#### Scenario: Faint fridge light counts at the default threshold
- **WHEN** no setup result is stored, `DOOR_THRESHOLD` is unset, zones are `0.0,0.0,1.0,1.0`, and a still is grey except a `(40,90,200)` block covering 1.5% of the zone
- **THEN** that still is open (1.5% is at least the 0.01 default), and the event counts as a door opening

#### Scenario: Stored color setup still works
- **WHEN** setup for the device stored a zone with `color` above 0.05 and a still has a `(220,170,40)` block covering 10% of that zone
- **THEN** that still is open, because the stored rule's feature is `color`
