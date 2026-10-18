# Proposal

## Why

On 2026-10-18 the owner changed the camera's privacy mask without moving the camera. Within three door openings the app showed "The camera has moved or changed angle". The device's alignment read `moved = true` with `failures = 3` and a shift of `(0, 0)`. The cause: the closed anchor is an edge map of the whole frame, so the new mask border and the changed black area count as differences. Every event's best error was 0.068–0.072, over the 0.05 limit, even though the right shift is `(0, 0)`. Run on the same clip with masked pixels left out, the comparison finds `(0, 0)` again.

A privacy mask change is normal owner behavior, and it should not be reported as a camera move. It only matters when the new mask hides part of a door zone, and then the owner needs to be told that, and which zone.

The second banner ("Open/close detection doesn't match the camera's recordings…") had a different cause. In all three clips the owner stood in front of the zones from the first frame to the last, so the setup's `change` rules read open throughout. That is out of scope here (see design, Open Questions).

Track: **Ring** (door detection on Ring clips), with **AWS Builder** for the backend pieces.

## What Changes

- Setup stores a **visible map** next to the closed anchor: which 128×72 pixels the privacy mask does not cover. Ring overlay text inside the masked area counts as masked. A setup stored before this change gets its map from the newest closed reference the first time it is needed.
- Event alignment compares only the pixels visible in both the anchor and the bookend, and averages the error over those pixels. It gets its own error limit, set from recorded clips.
- A **privacy mask change** is detected when the bookend's visible map differs from the anchor's on 2 events in a row. If the new mask hides part of a door zone, the alignment stores those zone names. If no zone is affected, the new map is adopted and nothing is shown.
- New setup warning `privacy_mask_changed`, which names the affected zones and links to the door setup. A mask change never produces `camera_moved`.
- One-off cleanup in prod, with Jayson's OK: clear the false `moved` state the mask change left on the fridge camera.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `door-self-calibration`: the anchor gets a visible map, alignment ignores masked pixels, and a mask change is detected separately from a camera move
- `setup-warnings`: new `privacy_mask_changed` warning
- `inventory-app`: a banner for `privacy_mask_changed` with a link to the door setup

## Out of scope

- Reading the privacy-zone geometry from the Ring API. The device's capabilities list `privacy_zones`, but neither the capabilities nor the configurations return the zones' shapes, so the mask is read from the frames.
- Suspect clips caused by a person blocking the zones for a whole clip, and the `door_setup_mismatch` warning they trigger
- Moving zones automatically out of a newly masked area
- Changes to the `camera_moved` rules for a real move (3 failures or a shift of at least 0.04)

## Impact

- `backend/src/fridgesense/alignment.py`: visible map, masked error, mask-change state
- `backend/src/fridgesense/door_calibration.py`: store the visible map at setup and backfill it for an existing setup
- `backend/src/fridgesense/door_events.py`: pass the visible maps into alignment
- `backend/src/fridgesense/setup_warnings.py`: `privacy_mask_changed`
- `pwa/src/api/types.ts`, `pwa/src/components/Warnings.tsx`, `pwa/scripts/mock-api.ts`: the new banner
- DynamoDB: new attributes on the `DOORSETUP#` item (`anchor_visible`) and the `ALIGN#` item (`mask_changed_at`, `mask_zones`, `mask_streak`). No new items.
- This builds on the unarchived `door-auto-calibration` and `door-calibration-from-clips` changes, which own the anchor, alignment and suspect-clip requirements.
