# Proposal

## Why

The door check's zones and threshold are fixed numbers, measured by hand from one recorded clip and set through CDK context. If the camera moves, or someone else installs it, openings are dropped, and the only fix is to re-measure pixels and redeploy. The owner should be able to teach the system what "open" and "closed" look like for their fridge, from the app, using the camera itself.

Reference images for the LLM can only come from a photo on the phone today. A snapshot from the fridge camera shows items the way Nova will see them. The owner also can't point at the part of a photo that matters.

Each motion event is judged from only 4 stills, and `opened_at`/`closed_at` come from Ring's motion window, not from when the door was actually open. Sampling about one still per second gives the real open and close times. Ring still downloads are free, and no LLM is involved.

## What Changes

- **Config screen gets two tabs:**
  - **"Reference images"** (today's content: reference images and custom instructions for the LLM analysis). Adding a reference now offers **"Choose photo"** or **"Camera snapshot"**. Before saving, the owner can draw boxes and lines on the image. The drawing is flattened into the uploaded JPEG, so Nova sees it.
  - **"Open/close detection"**: a list of *door references*. Each is a camera snapshot with one box drawn around a fridge door or drawer and a label, **Open** or **Closed**. The owner adds and removes them, then taps **"Run setup"**. Setup works out the zones and threshold from the references and shows how well open and closed separate.
- **New API routes:** `POST /api/camera/snapshot` (owner; a face-blurred still from the camera, not stored), and `GET /api/door-calibration`, `POST /api/door-calibration/references`, `DELETE /api/door-calibration/references/{id}` and `POST /api/door-calibration/run` (owner writes). Door references and the setup result are stored per Ring account and device in DynamoDB.
- **The door check uses the setup result** (zones and threshold) for the event's device. With no setup result, it falls back to `DOOR_ZONES`/`DOOR_THRESHOLD` or the built-in defaults, as today. The colorful-pixel rule does not change.
- **Denser sampling:** stills are requested every `STILL_INTERVAL_MS` (default 1000 ms) across the motion window, up to 30 per event, downloaded in parallel, and each one is scored.
- **BREAKING (data meaning):** a door event's `opened_at` is the time of the first still that scores as open, and `closed_at` is the time of the first closed still after the last open one (or the window end). `duration_s` follows. Events stored before this change keep their window-based times.
- **The stills sent on are picked from the open span:** up to 4, evenly spaced from the first open still through the closing still. Face detection, S3 and Nova cost per opening stay the same.

## Capabilities

### New Capabilities

- `door-calibration`: camera snapshots, the owner's labeled door references, and the setup run that turns them into the door check's zones and threshold, stored per account and device and served over the HTTP API.

### Modified Capabilities

- `door-event-detection`: "Stills across the opening" moves to interval sampling with the stills sent on picked from the open span. "Door-open check before any analysis" uses the device's setup result first. "Door event record" takes `opened_at`, `closed_at` and `duration_s` from the scored stills.
- `inventory-app`: "Config screen" becomes two tabs. "Manage reference images" gains the camera snapshot and drawing on the image. A new requirement covers the Open/close detection tab.

## Impact

- **Backend:** new `backend/src/fridgesense/door_calibration.py` (references, validation, setup run) and `camera.py` (snapshot: download, blur, downscale), new routes in `handlers/api.py`, and in `door_events.py` the sampling, parallel download, open-span selection and per-device setup lookup. `handlers/pipeline.py` reads `STILL_INTERVAL_MS`.
- **PWA:** `screens/Config.tsx` split into tabs (`#config` and `#config/doors`). New `DoorDetection.tsx`, a shared drawing component `ImageMarkup.tsx`, and pure geometry in `pwa/src/shapes.ts`. Updates to `AddReference`, `api/client.ts` and `api/types.ts`.
- **Infra:** `STILL_INTERVAL_MS` on the fetch-stills Lambda. The API Lambda gets Rekognition `DetectFaces`, its timeout goes from 10 s to 25 s for the snapshot, and it gets `DOOR_ZONES`/`DOOR_THRESHOLD` for the defaults it reports.
- **Ring:** up to 30 still requests per motion event instead of 4, well under the 100 requests-per-second limit. Whether stills 1 s apart are distinct frames is unverified; see design.md.
- **Cost:** unchanged per opening. Each snapshot costs one face-detection call (about $0.001).
- **Deploy:** this change's final deploy also covers `door-check-color-zones`, which is merged into `local` but not deployed yet.

**Hackathon tracks:** Ring (camera snapshots and setup from the app, and motion events turned into exact door-open times) and AWS Builder.

**Out of scope:**
- Watching the camera continuously or through live view (WHEP). Monitoring stays triggered by motion events.
- Tuning the colorful-pixel rule itself (its chroma and brightness limits) in setup. Setup picks only the zones and the threshold.
- Choosing between several cameras: the account's first discovered device is used.
- Polygons or freehand drawing for door references (one rectangle each), editing a door reference after it is added, and night or infrared mode.
- Re-analysing old events after a new setup run.
