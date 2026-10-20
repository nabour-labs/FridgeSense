# Proposal

## Why

`door-calibration-from-clips` made the Open/close detection sheets take their picture only from a recent clip, and made setup refuse any zone or reference drawn on a live picture. The owner wants the same choice the Fridge area sheet gives: a live snapshot straight away, or a frame from a recent clip. Clips can take a while to list, and on a new install there may be none yet. Then the door setup can't be done at all.

## What Changes

- **Both sources in the door sheets.** "Add zone", "Edit zone" and "Add reference" open with a live snapshot, as the Fridge area sheet does. Under the picture, "New snapshot" takes another live snapshot and "Recent clip" opens the "Snapshot from a recent clip" picker. The app sends `source = "live"` or `source = "clip"`, matching where the shown picture came from. Cancelling the picker keeps the sheet and whatever picture it shows.
- **Setup accepts live pictures.** `POST /api/door-calibration/run` no longer refuses zones or references with `source = "live"`. The requirement "Setup needs zones and references from clips" is removed.
- **Soft note instead of a block.** A live zone or reference shows "Live picture: may not line up with clips" instead of "Replace with a clip frame", and "Run setup" is no longer disabled because of it. The clip-wide sanity guard and the `door_setup_mismatch` warning from `door-calibration-from-clips` still catch a setup that doesn't match the clips.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-app`: door sheets offer a live snapshot and a recent clip; live pictures are noted, not blocked.
- `door-calibration`: setup no longer refuses live pictures.
- `camera-snapshot`: the Open/close detection sheets take a live frame again.

## Hackathon tracks

Ring (live view and recorded clips both used for setup).

## Out of scope

- Converting or aligning live pictures to clip framing.
- The Fridge area and Reference images sheets: unchanged.
- The door check, suspect guard and mismatch warning: unchanged.

## Impact

- **PWA:** `screens/DoorDetection.tsx` (picture source in the sheets, soft note, Run setup no longer blocked), `api/client.ts` (`source` passed in by the caller).
- **Backend:** `door_calibration.run` drops the live refusal.
- **Depends on:** `door-calibration-from-clips` (merged into `local`, not archived). Archive it before this change, since this change modifies and removes requirements it adds.
- **Cost:** none.
