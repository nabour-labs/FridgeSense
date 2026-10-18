# Spec Delta

## ADDED Requirements

### Requirement: Visible map stored with the anchor
A successful setup run SHALL store, with the closed anchor, the *visible map* of the same newest closed reference: a 128×72 map of the pixels the privacy mask does not cover. A pixel SHALL count as masked when at least 80% of the pixels in its 9×9 neighborhood have a gray value below 16, with the masked area then grown by 2 px. Ring's overlay text inside a masked area SHALL therefore count as masked. When a stored setup has an anchor but no visible map, the system SHALL build the map from the newest closed reference the first time an event is aligned, store it on the setup, and use it from then on. If no closed reference is left, every pixel SHALL count as visible.

#### Scenario: Map from the newest closed reference
- **WHEN** setup runs and the newest closed reference is black in its left 30% and right 35% columns
- **THEN** the stored visible map has 0 in those columns, grown by 2 px, and 1 everywhere else

#### Scenario: Overlay text in the mask stays masked
- **WHEN** the reference's black right-hand area holds three lines of white overlay text 2 px high
- **THEN** the text pixels are masked in the visible map

#### Scenario: Dark but unmasked detail stays visible
- **WHEN** the visible part of the reference holds a dark 4×4 px object on a light background
- **THEN** the object's pixels are visible in the map

#### Scenario: Setup stored before visible maps
- **WHEN** an event is aligned for a device whose stored setup has an anchor and no `anchor_visible`, and its newest closed reference is half black
- **THEN** the map built from that reference is stored as `anchor_visible` on the setup and used for this event

#### Scenario: No closed reference left for the backfill
- **WHEN** the stored setup has no `anchor_visible` and the device has no closed reference
- **THEN** alignment treats every pixel as visible and stores nothing

### Requirement: Alignment ignores masked pixels and blocked views
Event alignment SHALL compare the anchor with each bookend in 8×8 px blocks at 128×72, over every whole-pixel shift from −8 to +8 on both axes. A block SHALL count only if it lies wholly inside the visible map of the anchor and, after the shift, wholly inside the visible map of the bookend, and if its mean anchor edge value is at least 8 (blocks with no edges say nothing about a shift). A counted block *matches* when its mean absolute edge difference divided by 255 is at most 0.12. A shift's *match share* is matched blocks divided by counted blocks. For each bookend the shift with the highest match share wins, and ties keep the smaller move. The bookend with the higher share is used. Alignment SHALL succeed when that share is at least `ALIGN_MIN_MATCH` (default 0.5). The stored `error` SHALL be `1 − share`. With fewer than 8 counted blocks, alignment SHALL fail.

#### Scenario: Wider mask after setup
- **WHEN** the anchor's source image and the bookend are the same view, but the bookend is also black in a further 6% of columns on each side of the visible strip
- **THEN** alignment succeeds with shift `(0, 0)`

#### Scenario: Known shift with a mask
- **WHEN** the bookend is the anchor's masked test pattern shifted 3 px right and 1 px down, with the mask in the same place on the screen
- **THEN** alignment succeeds with `dx = 0.023` and `dy = 0.014` (±0.001)

#### Scenario: Person in front of the zones in both bookends
- **WHEN** both bookends show the anchor's view unshifted with a person covering 35% of the counted blocks
- **THEN** alignment succeeds with shift `(0, 0)`

#### Scenario: Rotated camera still fails
- **WHEN** both bookends are the anchor's source image rotated 5°
- **THEN** the best match share is below 0.5 and alignment fails

#### Scenario: Too little left to compare
- **WHEN** the bookend's visible map leaves fewer than 8 countable blocks shared with the anchor
- **THEN** alignment fails

#### Scenario: Recorded clip after a mask change
- **WHEN** the anchor is the recorded closed reference fixture and the bookends are the first and last frames of the recorded clip taken after the 2026-10-18 mask change
- **THEN** alignment succeeds with shift `(0, 0)`

### Requirement: Privacy mask change detected
After each event with an alignment attempt, the system SHALL compare the used bookend's visible map with the anchor's. The mask SHALL count as *changed* for that event when the two maps differ in more than 3% of pixels. Two changed events in a row SHALL confirm a mask change, and one unchanged event SHALL reset the count (`mask_streak`). On a confirmed change, the system SHALL find the *affected zones*: zones with less than 95% of their box visible in the new map. With no affected zone, the new map SHALL replace `anchor_visible` and nothing else SHALL change. With affected zones, the alignment SHALL store `mask_changed_at` (the confirming event's start) and `mask_zones` (the zone names, in setup order), and `anchor_visible` SHALL stay as it is. A successful setup run SHALL clear `mask_changed_at`, `mask_zones` and `mask_streak`. A mask change SHALL NOT count as a camera move.

#### Scenario: Mask change that misses every zone
- **WHEN** two events in a row have bookends whose visible maps differ from the anchor's in 13% of pixels, and every zone stays fully visible
- **THEN** `anchor_visible` is replaced by the second event's map, `mask_zones` is empty, and `moved` stays false

#### Scenario: Mask change that covers a zone
- **WHEN** two events in a row show a new mask that hides the left 40% of zone "Chiller", and the other zones stay fully visible
- **THEN** the alignment reads `mask_zones = ["Chiller"]` with `mask_changed_at` the second event's start, and `anchor_visible` is unchanged

#### Scenario: One odd event
- **WHEN** one event's visible map differs by 10% and the next event's differs by 1%
- **THEN** `mask_streak` is 0 and nothing else changes

#### Scenario: Small difference ignored
- **WHEN** two events in a row have visible maps that differ from the anchor's in 2% of pixels
- **THEN** no mask change is recorded

#### Scenario: Setup run clears the mask change
- **WHEN** `mask_zones = ["Chiller"]` and the owner runs setup successfully
- **THEN** `mask_zones` is empty, `mask_changed_at` is null, `mask_streak` is 0, and `anchor_visible` is the new newest closed reference's map

#### Scenario: Mask change while the camera also moved
- **WHEN** the mask changes and three events in a row also fail to align
- **THEN** both `moved = true` and the mask change are recorded
