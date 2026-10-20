# Spec Delta

## ADDED Requirements

### Requirement: Blocked suspect clips leave the streak unchanged
For a suspect clip with a stored closed anchor, the system SHALL check each bookend (the first and last checked frames) that reads open. At such a bookend, a zone that reads open *looks closed* when the mean absolute difference between the bookend's edge map and the anchor inside the zone's box (after the event's alignment shift, at 128×72), divided by 255, is at most `ZONE_CLOSED_MAX_DIFF` (default 0.05). The clip SHALL be *blocked* when it has at least one open bookend and no open-reading zone at any open bookend looks closed. A blocked clip SHALL leave `suspect_streak` unchanged and SHALL log `door_check_blocked` with `frames`, `open_share` and `zones_source`. Every other suspect clip SHALL add 1 to the streak, as before. A blocked clip SHALL otherwise be handled as any suspect clip: re-scored with the fridge light, `suspect = true` in the run output, and no self-tuning sample.

#### Scenario: Person in front of the zones at both bookends
- **WHEN** setup rules read every frame of a 41-frame clip open, and at both bookends the zone's edge difference from the anchor is 0.15
- **THEN** the clip is blocked, `suspect_streak` stays 2 (its value before), a `door_check_blocked` line is logged, and the outcome comes from the fridge-light re-score

#### Scenario: Wrong rules on a clear view
- **WHEN** setup rules read every frame of a 41-frame clip open, and at the first bookend the zone's edge difference from the anchor is 0.01
- **THEN** the clip is not blocked and `suspect_streak` goes from 2 to 3

#### Scenario: One bookend clear is enough to count
- **WHEN** both bookends read open, the first bookend's zone differs from the anchor by 0.15 and the last bookend's zone by 0.02
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: Two zones, only the open one is checked
- **WHEN** at both bookends zone A reads open and differs from the anchor by 0.12, and zone B reads closed and differs by 0.0
- **THEN** the clip is blocked

#### Scenario: Shift applied to the zone box
- **WHEN** the event aligned with a shift of 4 px right and the bookend is the anchor's view moved 4 px right, with the rules reading it open
- **THEN** the zone looks closed (difference ≤ 0.05) and the clip counts toward the streak

#### Scenario: Suspect by share alone
- **WHEN** a 100-frame clip is closed at frames 1–8 and 100 and open in between under setup rules (so it is suspect by its open share, with no open bookend)
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: No anchor stored
- **WHEN** a suspect clip comes from a device whose setup has no anchor
- **THEN** the clip is not blocked and the streak goes up by 1

#### Scenario: Recorded clip with the owner in front
- **WHEN** the anchor is the recorded closed reference fixture, the bookends are the recorded first and last frames from 2026-10-18, and the rules are the prod setup's three `change` zones reading open
- **THEN** the clip is blocked
