# Proposal

## Why

Setup gives the door check fixed numbers: zone boxes as fractions of the image, and a 32×32 "closed" baseline per zone. When the camera is bumped even a few pixels, the boxes land partly on the wrong thing and the baseline no longer lines up. Openings are then missed or invented, and nothing tells the owner. The owner also gets no warning about two other silent failures: motion detection switched off on the camera (Ring then creates no events, so nothing is ever recorded), and open/close setup never having been run.

Every event clip already starts and ends with the door closed, and the door check already decodes its frames. That is enough to keep the setup lined up with the camera, and to learn from recent openings, without any extra Ring calls or LLM cost.

## What Changes

- **Zones follow the camera (auto-alignment).** When setup runs, it also stores a small edge image of the whole frame with the doors closed: the *closed anchor*. For each motion event, the first and last decoded frames are compared with the anchor over shifts of up to ±8 px (at 128×72). If they line up well, every zone box is moved by that shift for this event's door check. The shift is stored per device and shown on the Open/close detection tab.
- **Camera-moved detection.** The camera counts as *moved* when alignment fails on 3 events in a row (rotation, zoom or a big move), or when the shift it applies reaches 4% of the frame on either axis. A moved camera raises a warning that asks the owner to update the door references (re-run setup) and the fridge area. Running setup again stores a new anchor and clears the door half of the warning. Saving the fridge area again clears the fridge half.
- **Self-tuning from recent activity.** Each event leaves a *sample* per zone: the closed bookend frame (used only if the current rule also says closed), and the frame that differs most from it (counted as open only if the difference is clear). The newest 20 samples are kept per device. After each new sample, setup's existing rule choice is re-run on the owner's references plus the samples. The new rules replace the current ones only if every zone still separates open from closed by the minimum margin. Otherwise the current rules stay. Re-running setup by hand discards the tuned rules and the samples.
- **Setup warnings.** A new `GET /api/warnings` returns a list of current problems:
  - `motion_detection_off`: Ring reports motion detection is off, so no clips are created.
  - `door_setup_missing`: open/close setup was never run.
  - `camera_moved`: the camera moved or changed angle, with which references need updating.
- **The app shows the warnings** as banners on the Fridge screen and the Config screen. Each banner links to the place that fixes it: the Camera tab, Open/close detection or Fridge area.
- `GET /api/door-calibration` also reports the alignment (shift, last checked, moved) and the tuning (when, from how many samples).

## Capabilities

### New Capabilities

- `door-self-calibration`: the closed anchor, per-event alignment of the door zones, camera-moved detection, and self-tuning of the door rules from recent event samples, stored per account and device.
- `setup-warnings`: `GET /api/warnings`, the list of setup problems (motion detection off, no door setup, camera moved) with what fixes each.

### Modified Capabilities

- `door-event-detection`: a new requirement for the door check to use the aligned zones and the tuned rules, and to record a sample for each event.
- `inventory-app`: a new requirement for the warning banners on the Fridge and Config screens.

## Impact

- **Backend:** new `backend/src/fridgesense/alignment.py` (anchor, shift search, moved state) and `self_tuning.py` (samples, retune). `door_calibration.run` stores the anchor and clears the tuned rules and samples. `door_calibration.setup_check` returns shifted, tuned rules. `door_events.fetch_stills` aligns before scoring, then records the sample and retunes after the event is claimed. New `backend/src/fridgesense/setup_warnings.py` and a `GET /api/warnings` route in `handlers/api.py`, using `camera_info.fetch_device` for motion detection. Door traces record the shift and alignment error.
- **Data:** DynamoDB items `ALIGN#{device}` (latest shift, failure streak, moved since) and `DOORSAMPLE#{device}#{ms}` (newest 20 kept). The setup item gains `anchor`, `tuned_zones` and `tuned_at`.
- **PWA:** new `components/Warnings.tsx` used by `screens/Fridge.tsx` and `screens/Config.tsx`, plus `warnings()` in `api/client.ts` and its types. `DoorDetection.tsx` shows the alignment and tuning lines.
- **Infra:** none. The pipeline Lambda already reads and writes the table, and the API Lambda already calls Ring.
- **Ring:** `GET /api/warnings` makes one device call (the same one as the Camera tab). There are no extra calls per event.
- **Cost:** no Bedrock calls are added. Each event adds one small DynamoDB read and two writes.
- **Order:** builds on `door-zone-setup` and `fridge-crop-box`, which should be archived first. This change only adds requirements, so it does not edit theirs.

**Hackathon tracks:** Ring (motion events keep a camera-based setup accurate, and the camera's motion-detection setting is checked) and AWS Builder.

**Out of scope:**
- Correcting rotation or zoom. Those are detected (alignment fails) and reported, not corrected.
- Moving the fridge area box automatically, or cropping with it.
- Turning motion detection on from the app. The warning tells the owner to do it in the Ring app.
- Push notifications or email for warnings. They show only in the app.
- Re-analysing past events with new rules.
- Warnings for more than one camera: the account's first discovered device is used, as in setup.
