# Design

## Context

- `door_calibration.run` turns the owner's references into `SetupZone`s (box, feature, direction, threshold, margin, 32×32 baseline) and stores them in `DOORSETUP#{device}`. `setup_check` turns them into a `DoorCheck` of `ZoneRule`s.
- `door_events.fetch_stills` picks the device's check through `_device_check`, decodes the clip's frames every 500 ms (`clip_frames_checked`), scoring each frame as it is decoded, and then claims the event. Stills sampling is the fallback.
- `camera_info.fetch_device` already parses Ring's `motion_detection` setting (`True`/`False`/`None`).
- `fridge_area.load` returns the area with `updated_at`.
- Pillow is the only image library. There is no numpy, and the Lambda package size matters.

## Goals / Non-Goals

**Goals:**
- Correct a translation of a few percent of the frame with no owner action.
- Detect rotation, zoom or a big move, and tell the owner instead of guessing.
- Keep the door check's per-event cost at a few hundred ms of extra CPU, with no extra Ring or Bedrock calls.
- Make every part testable with synthetic images.

**Non-Goals:**
- Sub-pixel accuracy, or correcting rotation or scale.
- Learning without owner references. Tuning always includes them as anchors of truth.

## Decisions

### Alignment on edge maps, brute-force search, Pillow only
Both images are scaled to 128×72 grayscale, then `ImageFilter.FIND_EDGES` is applied, then the result is autocontrasted. For each shift in −8..+8 on both axes (289 shifts), the mean absolute difference over the overlapping area is computed with `ImageChops.difference` on crops, plus `ImageStat`. That is roughly 300 small diffs, a few ms each, so well under 1 s per bookend.
- *Why edges:* the interior light and day/night ambient change brightness much more than they change edges. Comparing raw grayscale would make lighting look like movement.
- *Alternatives:* phase correlation (needs numpy FFT, so a new dependency); feature matching such as ORB (needs OpenCV, too large for Lambda); a coarse-to-fine pyramid (unnecessary at 289 shifts).
- `ALIGN_MAX_ERROR = 0.05`, measured in task 1.1 on the 12 local clips (2560×1440). Unshifted, shifted 3 and 6 px, darkened to 60%, and the worst frame with a person in view all scored 0.004–0.037, with the shift always found exactly. Rotations of 5° and 15° scored 0.075–0.091. The first pick of 0.08 would have let a 5° rotation through.

### Bookends as the closed truth
Ring triggers on someone approaching, so the first and last frames are almost always the door closed. Using the better of the two absorbs one bookend having a person in it. If both are bad, alignment fails, which only counts toward "moved" after 3 events in a row. That way one odd clip never raises a warning.

### Alignment applied per event, stored as the latest value
The shift used for this event is this event's own estimate when it succeeds, otherwise the last stored one. That handles a bump between two events right away. There is no smoothing: at a whole-pixel search the estimate is stable for an unchanged camera.

### Moved state, kept separate from the setup item
`ALIGN#{device}` holds `dx`, `dy`, `error`, `failures`, `moved`, `moved_at`, `last_moved_at` and `checked_at`. It is written by the pipeline on every event and reset by `run`. Keeping it out of `DOORSETUP` means a pipeline write never races the owner's setup write over the same item. `last_moved_at` survives a setup run, so the fridge-area half of the warning outlives the door half.
- The 4% shift limit counts as "moved" even though it is corrected. Past that shift, the owner's reference images and the fridge area box are visibly off, and the next small bump could exceed the ±8 px search.

### Samples and re-tuning
- `DOORSAMPLE#{device}#{start_ms:013d}` holds, per zone, `closed` and `open` as `{color, blue, brightness, thumb}` or null. Thumbs are 32×32×3 = 3 KB, so at most 6 zones × 2 × 3 KB ≈ 36 KB per item. Only the newest 20 are kept: after a put, query the prefix and delete beyond 20.
- The open sample uses `change` from the closed bookend, not the current rule. That avoids circular labels: a rule that misses openings can't teach itself to keep missing them. It also means the missed-opening case (outcome `not_door`) produces the samples that fix it.
- The closed sample *is* confirmed by the current rule. This guards against a clip that starts with the door already open. Being wrong here just drops one closed sample.
- The re-tune reuses `door_calibration._choose` and `baseline_of` on combined value lists. Owner references are measured at their own boxes, samples at the shifted boxes. Both describe the same physical door.
- Adoption guard: every zone must separate with margin ≥ `MIN_MARGIN`. Because the owner's references are in the set, a tuned rule always classifies them correctly. If it fails, the last good rules stay, and `door_retune_skipped` is logged with the zone and its best margin.
- Tuned rules live in the setup item as `tuned_zones`, `tuned_at` and `tuned_from`. `run` overwrites the whole item, so a manual run discards them naturally. It also deletes the samples.
- *Alternative considered:* an exponential moving threshold. It is simpler, but it can't switch features, and it drifts toward whatever the rule already believes.

### Ordering inside `fetch_stills`
1. Load the check and the stored shift. 2. Decode and score the frames with the stored shift (frames are still scored as they are decoded, so a decoded clip is never held). 3. Align the first and last kept JPEG frames with the anchor. 4. If that gives a different shift, re-score the kept JPEG frames with it.
Re-scoring happens only when the camera moved since the last event, and the JPEGs are already in memory. This is simpler than aligning on the first frame before decoding the rest, and gives the same result. In the stills fallback, all stills are downloaded before scoring, so they are aligned first.
Sampling and re-tuning run after the claim transaction, each wrapped in try/except so they cannot change the outcome.

### Warnings endpoint
`warnings.py` composes three checks: `fetch_device` (Ring), `load_setup`, and `ALIGN` plus `fridge_area.load`. It reuses `camera_info.fetch_device`, so Ring failures are already handled and return None. It is a separate endpoint rather than part of `/api/camera`, so the Fridge screen does one small request, and the Camera tab's contract doesn't change.

### PWA
One `Warnings` component takes the role (owner/viewer) from `AppContext` and renders the banners. It is used at the top of `Fridge.tsx` and of `Config.tsx` (above the tabs). It loads once per screen visit through `useLoad`, not on the Fridge screen's 10 s poll, so polling causes no extra Ring calls.

## Risks / Trade-offs

- [Lighting at night (IR mode) changes edges] → Rotation-like errors raise `failures`, but 3 in a row are needed, and one good daytime event resets it. Night mode is out of scope in setup too. Test 1.1 measures the real error.
- [Someone standing in front for a whole clip] → Both bookends are bad, so alignment fails and no sample is stored. That only counts toward moved after 3 events in a row.
- [Wrong open samples (a person close to the zone)] → They can only stop a re-tune (no separation), never adopt a rule that misclassifies the owner's references.
- [Extra CPU per event] → 2 × 289 small diffs plus one re-tune over at most 20 samples. Measured in task 2.x. The pipeline Lambda's 90 s budget has ample room.
- [DynamoDB item size] → Samples stay ≤ 36 KB. The anchor is 9 KB in the setup item, next to 6 baselines of 3 KB each.
- [Tuning drifts away from what the owner set] → The tab shows "Tuned from N recent openings". Re-running setup resets to the owner's rules.

## Migration Plan

- Devices that ran setup before this change have no anchor. Alignment is skipped and no samples are stored until the owner runs setup again, and `door_setup_missing` doesn't fire because a setup result exists. The demo device just needs setup re-run once after deploy.
- Rollback: redeploy the previous version. The new items (`ALIGN#`, `DOORSAMPLE#`, and the setup item's extra fields) are ignored by the old code.

## Test strategy

- **Unit (pytest, `backend/tests/`):**
  - `test_alignment.py`: synthetic 1280×720 test patterns (a grid plus shapes) shifted by known pixels, darkened to 60%, rotated 15°, and with a grey block "person". Covers the shift search, the bookend choice, the error limit, the moved and failure state machine, and the clamped zone shift.
  - `test_self_tuning.py`: open, closed and person samples built from the colors already used in the door-calibration scenarios. Covers keeping 20 samples, adopting tuned rules, skipping on overlap, too few samples, and the reset on run.
  - `test_warnings.py`: Ring device responses from canned JSON fixtures (`tests/fixtures/ring/device_motion_off.json`, `device_motion_on.json`), plus a timeout and a 500 through a stubbed `RingClient`. Setup, alignment and fridge area states go through moto DynamoDB.
- **Contract (API handler tests):** `test_api_warnings.py` for `GET /api/warnings` (shape, order, 401, no device). `test_api_door_calibration.py` is extended for `alignment`, `tuned_at` and `tuned_from`.
- **Integration (pipeline, moto + stubbed Ring):** `test_door_events.py` gets an encoded test clip of the shifted scene. It is generated in a fixture with PyAV from synthetic frames, so no real clip is committed. Covers `door_open` with an anchor, `not_door` without one, a table error during alignment, a sample-write error, and the trace fields.
- **PWA (Vitest + Testing Library):** `Warnings.test.tsx` covers each banner, its links, the viewer, empty and 500 cases. `Fridge.test.tsx` and `Config.test.tsx` check the banner is mounted. `DoorDetection.test.tsx` covers the shift, tuned and moved lines.
- Nothing calls live Ring, AWS or Bedrock. The real `tmp/*.mp4` clips are used only locally in task 1.1 to pick `ALIGN_MAX_ERROR`, never in committed tests.

## Measured limits (task 1.1)

- Alignment error: aligned cases 0.004–0.037, rotated 0.075–0.091, so `ALIGN_MAX_ERROR = 0.05`.
- Zone `change` from the first frame (zone 1 of the default zones): real openings peaked at 0.104–0.216, and clips without a door-zone opening at 0.031–0.046. Closing frames were 0.007–0.031. The 0.08 open-sample limit sits between the two groups.
