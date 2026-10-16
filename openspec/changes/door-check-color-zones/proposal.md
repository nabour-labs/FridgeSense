# Proposal

## Why

Real fridge openings are being dropped as `motion_not_door`. On 2026-10-15 every motion event was rejected, with `brightest` values of 0.25–0.50 against a 0.5 threshold. A recorded clip (2026-10-15 19:20, 2560×1440) shows why:

- The current check averages brightness over a box, and that average stays flat at about 0.24 whether the fridge is closed or open. Ambient light moves the whole frame, and the open fridge adds dark door liners and a person in front.
- The camera's privacy mask blacks out everything outside a vertical strip at about 31–63% of the width. The default box (`0.25,0.1,0.5,0.8`) is mostly that black mask.

The fridge's interior light does give a reliable signal: grey stainless steel turns into a patch of colorful, blue-lit pixels. Measured in the clip, the fraction of colorful pixels was:

| | Doors zone | Drawers zone |
|---|---|---|
| Closed | ≤ 0.005 | 0.000 |
| French doors open | 0.13–0.39 | — |
| Middle drawer open | ~0.002 | 0.095–0.102 |
| Bottom drawer open | ~0.002 | 0.048–0.072 |

The masked strip also means every still sent to Nova, face detection and S3 is about two-thirds black. That costs image tokens and storage for nothing.

## What Changes

- **BREAKING (config):** The door-open check no longer uses mean brightness in one box. It counts the fraction of *colorful* pixels in each of a list of zones (by default one for the French doors and one for the drawers). An event counts as a door opening when any zone in any still reaches the threshold. The `DOOR_BOX` setting is replaced by `DOOR_ZONES`, and `DOOR_THRESHOLD` now means a fraction of colorful pixels (default 0.02).
- The `motion_not_door` log line and the `not_door` run output report the highest colorful fraction as `score` instead of `brightest`, along with the zone that produced it.
- New optional `STILL_CROP` setting (`x,y,width,height` fractions). When set, each still that passes the door check is cropped to that box **before** face detection, storage and analysis. When unset, stills are stored unchanged, as today.
- CDK context: `doorZones`, `doorThreshold` and `stillCrop` get defaults measured on this camera. `doorBox` goes away.
- The README's door-tuning section is rewritten for the new score.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-event-detection`: the "Door-open check before any analysis" requirement changes from box brightness to a colorful-pixel fraction over several zones. A new requirement crops stills to the visible strip. The face-blurring and stills requirements are adjusted so they apply to the cropped still.

## Impact

- **Code:** `backend/src/fridgesense/door_events.py` (`DoorCheck`, `fetch_stills`, `store_blurred_stills`), `backend/src/fridgesense/handlers/pipeline.py` (env parsing).
- **Infra:** `infra/lib/door-pipeline.ts` and `infra/lib/fridgesense-stack.ts` (environment variables and context), plus `infra/test/pipeline.test.ts`.
- **Tests:** `test_door_check.py`, `test_fetch_stills_task.py`, `test_pipeline_e2e.py` and the `jpeg` helper in `conftest.py`.
- **Docs:** README tuning section.
- **Cost:** cropping cuts each still to about 34% of its pixels, so fewer Nova image tokens and less S3 storage. Face detection is still priced per image, so its cost is unchanged.
- **Deploy:** needs a `cdk deploy` (with Jayson's OK) for the new environment variables.

**Hackathon tracks:** Ring (makes motion events from the camera usable at all) and AWS Builder (lower Nova and S3 cost per opening).

**Out of scope:**
- Night / infrared mode (kitchen lights off). Night-vision frames are greyscale, so this check will score them 0 and miss openings. Tuning for that waits on lights-off footage and gets its own change.
- Detecting the privacy mask automatically, or reading it from the Ring API. The crop box is configured by hand.
- Cropping reference images uploaded through the app.
- Fixing the `window_fallback` seen at 23:09 (Ring history had no matching event).
