# Design

## Context

See proposal.md (Why) for the measurements. The current pipeline in `door_events.fetch_stills` works like this: download up to 4 stills into memory, run `DoorCheck.evaluate` (mean brightness in one box), then for openings call `store_blurred_stills` (Rekognition, then S3), then Nova reads the stored objects. Configuration comes from Lambda environment variables (`DOOR_BOX`, `DOOR_THRESHOLD`), which CDK sets from context values with hard-coded defaults.

Ring stills from this camera are 2560×1440. The privacy mask is burned into the image as black, leaving content only at x ≈ 790–1610 px (0.31–0.63). The Ring logo and the timestamp overlay sit inside the masked area.

## Goals / Non-Goals

**Goals:**
- Catch French-door, middle-drawer and bottom-drawer openings in normal room light, with a wide margin over the closed fridge.
- Remove the masked area from everything after the door check.
- Keep the check cheap: Pillow only, a few milliseconds per still, no new dependency.

**Non-Goals:**
- Night or infrared frames. They are greyscale, so the score is 0. See Open Questions.
- Per-zone thresholds. One threshold is enough for the measured data, and a second number to tune is not worth it before the deadline.

## Decisions

**1. Colorful-pixel fraction instead of brightness or blue only.**
A pixel counts as colorful when its chroma (`max − min` of R, G and B) is above 60 and its brightest channel is above 100. Brushed steel, white cabinets and the wood floor are all low-chroma, and ambient light changes their brightness but not their hue. The interior LED is blue and the food packaging is colorful, so an opening shows up as chroma.
- *Blue only* (`B − R > 40`) was tried. It works for the French doors but scores only 0.02–0.04 on the bottom drawer, where food packaging dominates. The colorful-pixel test scores 0.05–0.07 there.
- *Relative brightness* (fridge box ÷ rest of the strip) was tried and did not separate open from closed (0.50–0.68 for both).
- *Difference against a closed reference image* was rejected: a person standing in front of a closed fridge changes as many pixels as an opening does.
- The brightest-channel floor of 100 keeps dark, saturated clothing (navy, maroon) from counting.

**2. Several zones, scored independently, best one wins.**
One large box dilutes a drawer opening, which covers about 5% of the fridge front, below any threshold that is safe against noise. Separate zones keep each opening a large share of its own zone. The zones are a `;`-separated list, so a third zone (for example, a freezer) needs only configuration. The score and the winning zone index are logged so tuning can see which zone fired.

**3. Zones are in uncropped-frame coordinates, and the door check runs before the crop.**
The zones then stay valid if `STILL_CROP` changes or is removed, and the existing order (check, then face detection, then storage) is unchanged. The alternative, cropping first, would tie two settings together for no gain.

**4. Crop before face detection, configured by hand.**
Cropping before Rekognition means face boxes are relative to the image that gets stored, so blurring needs no coordinate mapping. Detection is priced per image, not per pixel, so cropping saves nothing there, but S3 storage and Nova input both shrink to about 34% of the pixels. Auto-detecting black borders was rejected for now: at night the room itself can be near-black at the edges of the strip, and a fixed box is deterministic and testable. Re-encoding uses JPEG quality 95, the same as the face blurrer.

**5. Configuration and defaults.**
| Env var | CDK context | Code default | CDK default |
|---|---|---|---|
| `DOOR_ZONES` | `doorZones` | `0.38,0.32,0.21,0.30;0.455,0.60,0.12,0.18` | same |
| `DOOR_THRESHOLD` | `doorThreshold` | `0.02` | `0.02` |
| `STILL_CROP` | `stillCrop` | unset (no crop) | `0.30,0.0,0.34,1.0` |

The threshold of 0.02 sits about 4× above the worst closed-fridge frame (0.005) and about 2.5× below the weakest labeled opening (0.048, bottom drawer). The code leaves cropping off by default, so tests and other cameras behave as before. CDK turns it on for this deployment. `DOOR_BOX` and `doorBox` are removed rather than aliased, since nothing else reads them.

**6. Output field renamed.**
`brightest` becomes `score`, and `zone` is added, in both the `motion_not_door` log and the `not_door` run output. Nothing downstream (the Step Functions definition, the PWA, the API) reads `brightest`; only tests and the README do.

## Test strategy

- **Unit (`test_door_check.py`):** synthetic JPEGs from an extended `conftest.jpeg` helper (a solid RGB fill plus colored blocks at given fractions). These cover the colorful-pixel rule (bright grey, dark grey, navy, saturated blue, saturated red), the per-zone scoring and winning zone, the inclusive threshold, config parsing and its validation errors, and the defaults.
- **Unit (`test_stills.py` or a new `test_still_crop.py`):** crop dimensions and offset on a 2560×1440 synthetic still with a marker column, no-crop pass-through (identical bytes), and crop config validation.
- **Task level (`test_fetch_stills_task.py`):** with Ring stubbed (respx) and moto S3 and a stubbed Rekognition. Checks that a closed fridge gives `not_door` with `score` and `zone` in the log and no Rekognition call, and that with `STILL_CROP` set, both the Rekognition request bytes and the stored object are the crop.
- **End to end (`test_pipeline_e2e.py`):** the existing run with `DOOR_ZONES`/`DOOR_THRESHOLD` env vars, and stills that are colorful instead of bright. Also a run with `STILL_CROP` set, where the Nova request (stubbed Converse) carries the cropped image.
- **Infra (`infra/test/pipeline.test.ts`):** the Lambda environment has `DOOR_ZONES`, `DOOR_THRESHOLD` and `STILL_CROP` with the CDK defaults, and no `DOOR_BOX`.
- Nothing calls live Ring, AWS or Bedrock.

## Risks / Trade-offs

- [Night or infrared frames score 0, so every opening in a dark kitchen is missed] → Documented as out of scope. The lights-off footage the user will send drives a follow-up change, likely a greyscale fallback rule.
- [Brightly colored clothing or a colorful bag in front of the closed fridge scores as an opening] → The zones cover the fridge face only, and the cost of a false positive is one Nova call that reports no changes, which is already logged.
- [The camera moves or the mask changes, so the zones and crop go stale] → Both are CDK context values. The README tuning section explains how to re-measure from the `motion_not_door` scores.
- [Cropping wrongly could cut off part of the fridge] → The crop default has a 1–2% margin on each side of the measured strip. The crop is applied after the door check, so detection is never affected.
- [A still taken while a door is half-open scores low] → The check uses the best of 4 stills across the window, and the measured full-open frames have a 2.5× or larger margin.

## Migration Plan

1. Merge into `local` with tests green, then `cdk diff` to confirm only Lambda environment variables change.
2. `cdk deploy` (with Jayson's OK). Older context flags such as `-c doorBox=…` are ignored.
3. Open each door and drawer once. Check the pipeline log for `door_event_recorded` and look at a stored still to confirm the crop.
4. Rollback: redeploy the previous commit. No data migration is needed, and the door events already stored are unaffected.

## Open Questions

- Which rule catches openings in night or infrared mode (for example, a bright-pixel fraction on greyscale frames)? This waits on lights-off footage, and the answer adds a rule without changing this one.
