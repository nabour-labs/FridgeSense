# Proposal

## Why

Prod shows "Open/close detection doesn't match the camera's recordings…" with a suspect streak of 42, but the door rules are fine. In the traced clips from 2026-10-18 the owner stood in front of the fridge from the first frame to the last. The setup's `change` rules compare each zone with a closed baseline, so a person covering a zone reads as "open". The clip then reads open at both bookends and counts as suspect, and 3 in a row raise the mismatch warning. That warning tells the owner to redo the door references, which would not help.

Measured on those frames against the setup's closed anchor (mean edge difference inside each zone box, /255):

| Frame | Chiller | Freezer Drawer 1 | Freezer Drawer 2 |
|---|---|---|---|
| Closed references | 0.00–0.03 | 0.00–0.03 | 0.00–0.03 |
| Clip bookends, owner in front | 0.149–0.157 | 0.086–0.092 | 0.081–0.088 |

Wrong rules show up as a zone that reads open while it still looks just like the closed anchor. A blocked zone doesn't look like the anchor at all.

Track: **Ring** (door detection on Ring clips).

## What Changes

- A suspect clip counts toward the suspect streak only when some bookend reads open while one of its open-reading zones *looks closed* (zone edge difference from the anchor ≤ 0.05, after the event's shift). When every open-reading zone at the open bookends looks different from the anchor, the clip is *blocked*: the streak is left unchanged and a `door_check_blocked` line is logged.
- A blocked clip is still re-scored with the fridge light and still teaches nothing, as for any suspect clip. Only the streak, and so the warning, changes.
- Clips without an anchor, and suspect clips whose bookends both read closed (the ≥ 90%-open case), count as they do today.
- One-off prod cleanup, with Jayson's OK: reset the fridge camera's `suspect_streak` from 42 to 0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `door-event-detection`: blocked suspect clips leave the suspect streak unchanged

## Out of scope

- Changing which clips are suspect, or the fridge-light re-score
- Learning from blocked clips
- Telling a person apart from other blockers (a shopping bag, an open cupboard door)

## Impact

- `backend/src/fridgesense/door_events.py`: a zone-looks-closed check at the bookends, and the streak update in `fetch_stills`
- No API, PWA, IAM or table-shape changes
- Builds on the unarchived `door-calibration-from-clips` change (suspect clips and streak) and `privacy-mask-change` (anchor and alignment)
