# Design

## Context

`fetch_stills` scores every clip frame with the setup rules. `is_suspect` flags clips that read open at both bookends or in ≥ 90% of frames. `_count_suspect` adds the result to `suspect_streak`, and `setup_warnings.setup_mismatch` shows the banner at 3. A recording starts and ends with the doors closed, so an open bookend is taken as proof the rules are off. That breaks when something stands between the camera and the zones: the `change` and `brightness` features read the person, not the door.

The event already has what is needed to tell these apart: the closed anchor (edges at 128×72 from setup's newest closed reference) and the event's alignment shift.

## Goals / Non-Goals

**Goals:** a person in front of the fridge at both bookends doesn't raise the mismatch warning. Rules that are really wrong still raise it.

**Non-Goals:** changing what is suspect, the fridge-light re-score, or self-tuning.

## Decisions

### D1. Evidence = an open-reading zone that still looks closed
Wrong rules read "open" on a view that is plainly the closed fridge. Occlusion makes the zone look like something else. So only the zones that read open at an open bookend are checked, against the anchor inside the zone box. Measured on prod: closed references 0.00–0.03, owner-blocked bookends 0.081–0.157, open references 0.018–0.293. `ZONE_CLOSED_MAX_DIFF = 0.05` sits between the closed and blocked cases. An open door also differs from the anchor, so a recording that really starts with a door open counts as blocked too, which is correct: that isn't a rules problem either.

*Alternative:* the 8×8 block match share inside the zone. Rejected: zone boxes cover only 1–6 whole blocks at 128×72, too few for a share.

### D2. Blocked leaves the streak unchanged (no reset)
A blocked clip says nothing about the rules either way. Resetting would let wrong rules hide behind a few blocked clips, and counting is the bug being fixed.

### D3. Everything else about a suspect clip stays
The fridge-light re-score already gave the right outcome on the prod clips, and learning from an obstructed clip would still teach the wrong thing. Only `_count_suspect`'s input changes.

### D4. Uses the plain edge map, not the visible map
Zone boxes are inside the visible area by construction: the `privacy-mask-change` warning covers zones under the mask. A plain edge difference is enough here.

### D5. Prod cleanup
The streak is 42 and only drops on a normal clip or a setup run. After deploy, with Jayson's OK, `suspect_streak` on the fridge camera's `ALIGN#` item is set to 0 (one `UpdateItem`).

## Risks / Trade-offs

- [A half-open door that looks nearly closed] → the zone could look closed while the rules rightly read open at a bookend. That clip is counted as before, which is today's behavior.
- [Rules that are wrong only while someone stands there] → hidden by design. Such clips are still re-scored with the fridge light, so the outcome stays right.
- [No anchor (setup older than anchors)] → counted as before.

## Test strategy

- **Unit (pytest)**: `zone_looks_closed` / `is_blocked` in `door_events` on synthetic frames: a test pattern for the anchor, a flat "person" rectangle over the zone, the anchor shifted 4 px with the matching shift, and two zones with one open.
- **Recorded fixture**: `tests/fixtures/alignment/mask_change/` (closed reference and the 2026-10-18 bookends, already committed) with the prod setup's three zone boxes.
- **Integration**: `fetch_stills` with a served clip (as in `test_fetch_stills_clip.py`): a blocked suspect clip leaves the streak at its stored value and logs `door_check_blocked`. A clear-view miscalibrated clip still adds 1. No live Ring or AWS calls; moto table and respx.
