# Proposal

## Why

Inventory accuracy is poor because the door check counts every motion as a door opening. In the 61 door events recorded on 2026-10-17, every checked frame of every clip scored "open". So the 4 stills sent to Nova were spread across the whole motion event, and in 40 of the 50 analyzed events the door was closed in all 4 stills. Nova still reported changes for 24 of those 40.

The cause is the setup references. They are 960×540 frames from the live view or the Ring still, and these are framed differently from the recorded clips the door check scores (2560×1440). With the setup's `change` rule, a closed door in a clip differs from the "closed" baseline by about 0.09, double the 0.045 threshold. Using a closed *clip* frame as the baseline instead gives 0.016 for closed and 0.099 for open. The closed anchor used for camera alignment comes from the same mismatched reference. Alignment then "succeeds" with no shift (error 0.04 against a 0.05 limit), so it cannot correct the mismatch.

The `blue` (fridge-light) feature needs no baseline, so framing does not affect it. In evening clips it reads 0.000 with the door closed and 0.043–0.059 open. Its current pixel test is too loose for daylight, though: cool daylight on the steel doors reads about 0.10 with the door closed. A stricter test (blue lead > 60, chroma > 100, peak > 120) reads 0.000 on daylit steel and still 0.038 on the open interior.

## What Changes

- **Door setup images come from recorded clips.** In Open/close detection, the add-reference and zone sheets take their picture from a frame of a recent door-opening clip, using the existing recent-clip frame picker. They no longer use the live view or the Ring still. Zones and references record their `source` (`clip` or `live`). **BREAKING:** setup refuses to run while any zone or reference is not from a clip (422 naming the first one). The owner must redraw the zones and replace the references once.
- **Stricter fridge-light test.** The `blue` feature counts a pixel only when `B − max(R,G) > 60`, `max − min > 100` and `max > 120` (was 20 / 60 / 100). This applies to the default rule, to setup, to self-tuning and to the door check.
- **Fridge light preferred in setup.** When `blue` separates a zone's open and closed references by at least the minimum margin, setup picks `blue` for that zone even if another feature has a larger margin. `change`, `color` and `brightness` are used only when `blue` does not separate.
- **Clip-wide sanity guard.** A clip is *suspect* when its first and last checked frames are both open, or when at least 90% of its checked frames (and at least 10) are open. For a suspect clip with the device's setup rules, the door check scores the frames again with the fridge-light rule on the same zone boxes. It uses that result, logs `door_check_suspect`, and records no self-tuning sample.
- **Setup mismatch warning.** After 3 suspect events in a row, `GET /api/warnings` lists `door_setup_mismatch`, linking to Open/close detection. A non-suspect event or a new setup run clears the streak.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-calibration`: zones and references carry a `source`. Setup needs both to come from clips. `blue` uses the stricter pixel test and wins whenever it separates.
- `door-event-detection`: the stricter `blue` pixel test in the door check, and the clip-wide sanity guard with fallback to the fridge-light rule.
- `setup-warnings`: the `door_setup_mismatch` warning.
- `inventory-app`: the Open/close detection sheets take their image from a recent clip, older zones and references are marked for replacement, and the mismatch banner links to the fix.
- `camera-snapshot`: the Open/close detection sheets no longer take a live frame.

## Hackathon tracks

Ring (better use of Ring clips for detection) and AWS Builder: fewer false openings means fewer Bedrock Nova calls, each of which costs money.

## Out of scope

- Nova prompt and request changes: gating analysis on a visible open door, before/after frame choice, evidence fields and confidence calibration. These are a separate change.
- The FetchStills out-of-memory failure on 120 s clips, which leaves events stuck in `analyzing`. This is a separate change.
- Cleaning up the inventory and door events recorded while the door check was wrong.
- Re-recording or labelling a daylight door-open clip. The stricter thresholds are checked against the local labelled clips in `tmp/` (see design). If daylight openings fail, the thresholds change in this change before it is archived.
- Item reference images (Reference images tab) and the Fridge area snapshot: unchanged. The Fridge area box was also drawn on a live picture and may be offset in the same way. It only affects what Nova sees, not the door check, so it belongs with the Nova change.

## Impact

- **Backend:** `door_events.py` (blue constants, suspect guard and fallback re-score, `door_check_suspect` log, sample skipped when suspect). `door_calibration.py` (reference `source`, setup refusal, blue preference). `self_tuning.py` (same blue preference when re-tuning). `setup_warnings.py` (mismatch streak and warning). `handlers/api.py` (accept and return `source`). The door trace records `suspect` and the rule source used.
- **Data:** door zone and reference items gain `source`. The `ALIGN#{device}` item, or a sibling item, holds `suspect_streak`. Existing references have no `source` and read as `live`.
- **PWA:** `screens/DoorDetection.tsx` uses `camera/RecentClipPicker.tsx` in the add-reference and zone sheets, and marks `live` references with "Replace with a clip frame". New warning code in `components/Warnings.tsx`.
- **Depends on:** `door-zones-defined` and `door-auto-calibration` (merged into `local` but not archived) modify the same door-calibration requirements. Archive them before this change. This change only adds requirements to `door-calibration` so their deltas still apply.
- **Cost:** none added. Fewer false openings mean fewer Nova and Rekognition calls.
- **Owner action after deploy:** redraw the 3 door zones and replace the 9 door references with clip frames, then run setup again.
