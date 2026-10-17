# Proposal

## Why

The door check counts any colourful pixels in its zones, so food held in front of the closed fridge looks like an opening. On the 12 local recordings (draft labels, `door-detection-clip-tests`), a snack, a plate of food and a red packet made 4 of 344 stills read "open" while the doors were shut. That gives one false door event (clip 2023) and an opening that starts 2 s early (clip 1932). Each false event costs a Nova call and puts wrong items in the inventory. The fridge's LED-lit interior is blue, and food in a hand is warm-coloured. Counting only blue-lit colourful pixels at a threshold of 0.01 removed all 4 false opens and cut missed open stills from 6 to 3 on the same stills.

Hackathon track: Ring (more accurate open/close detection on the Ring Indoor Cam).

## What Changes

- New door-check feature **`blue`**: the fraction of a zone's pixels that are colourful (`max − min > 60` and `max > 100`) **and** blue-lit (`B − max(R, G) > 20`).
- **Default door check uses `blue`** instead of `color` when a device has no setup result. The default threshold drops from 0.02 to **0.01**, both in the backend and in the CDK `doorThreshold` context default that the stack passes as `DOOR_THRESHOLD`.
- **Door setup can choose `blue`**: it is measured for every zone with the other features, and wins ties (order: blue, color, change, brightness), so a device set up from references also ignores warm food.
- The Open/close detection tab labels the feature "Blue light". Debug traces of default rules show `feature = "blue"`.
- `color` stays available, so an existing stored setup result that uses it keeps working unchanged.

## Out of scope

- Splitting several openings in one window into separate door events.
- Changing the 30-still cap or the still interval.
- New or moved zones (the lower freezer drawer zone added nothing in the measurement).
- Re-running setup for devices that already have a setup result.
- Daylight footage: all 12 clips are from one evening. The risk is noted in the design.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-event-detection`: the door-open check without a setup result uses `blue` at 0.01, and setup rules may use `blue`.
- `door-calibration`: setup measures `blue` and prefers it on ties.
- `inventory-app`: the Open/close detection tab names the `blue` feature "Blue light".
- `pipeline-debug-traces`: default-rule traces list `feature = "blue"`.

## Impact

- `backend/src/fridgesense/door_events.py`: `measure`, `FEATURES`, the default `ZoneRule` feature, `DEFAULT_THRESHOLD`.
- `backend/src/fridgesense/door_calibration.py`: picks up the new feature through `FEATURES`.
- `pwa/src/api/types.ts` (`DoorFeature`) and `pwa/src/screens/DoorDetection.tsx` (label).
- `infra/lib/fridgesense-stack.ts` (`doorThreshold` default) and the infra tests that expect `"0.02"`.
- Tests: existing door-check, setup and trace tests that assume the default is `color` at 0.02 get updated through the spec scenarios. The clip tests and report from `door-detection-clip-tests` measure the result.
- Depends on `door-zone-setup` and `pipeline-debug-traces` (both unarchived; their requirements are modified here) and on `door-detection-clip-tests` (the harness and labels). No new AWS resources and no added cost.
