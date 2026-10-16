# Design

## Context

`door-check-color-zones` (archived, merged into `local`, not deployed) gives `DoorCheck(zones, threshold)` with the colorful-pixel score, `parse_box`, `colorful_fraction`, `crop_still` and `fetch_stills`, which downloads 4 stills one after another, checks them, then crops, blurs and stores them. Zones and threshold come only from env (`DOOR_ZONES`, `DOOR_THRESHOLD`). Door events take `opened_at`/`closed_at` from Ring's motion window.

Facts that shape the approach:
- The camera records only on motion, and Ring's image download returns existing footage only (the nearest frame within ±10 s). So a snapshot can fail when nothing moved recently.
- The API Lambda (`handlers/api.py`, 20 s timeout) reads the Ring token store (read-only: the token-refresh Lambda keeps it fresh) and the table, but has no Rekognition permission.
- Analysis references (`REF#…`) store base64 JPEGs of up to 200 KB in DynamoDB. The PWA shrinks photos with `image.ts::toJpeg` (768 px), injected as `resize` so tests avoid canvas.

## Goals / Non-Goals

**Goals:**
- One scoring function shared by setup and the pipeline, so the scores the owner sees are what the check does.
- Setup is deterministic and explainable: zones from the drawn boxes, and per zone the feature (color, brightness or change) whose open and closed reference values are furthest apart, with the threshold halfway between them.
- Drawing is pure geometry in a tested module. React components only turn pointer events into fractions.
- Fetch-stills runtime stays well inside the 90 s task timeout at 30 stills.

**Non-Goals:**
- Learning the colorful-pixel limits (chroma 60, peak 100), or any ML model.
- Storing snapshots server-side between the snapshot and the add (the client sends the image back).

## Decisions

**1. Snapshot is stateless and shared by both tabs.**
`POST /api/camera/snapshot` returns a blurred, downscaled JPEG and stores nothing. The Reference images tab resizes it to 768 px and flattens the drawing into it. The door tab posts it back unchanged with the box and status. Considered: storing the snapshot and returning an id. Rejected because it adds an item lifecycle (orphans) for no benefit, since the image only goes to the owner's own device and back. The blur runs before the image leaves the Lambda, so no unblurred still ever reaches the browser or storage.

**2. Snapshot image: at most 960 px wide, JPEG quality 85, re-encoded at 70 if over 250 KB.**
That keeps it under the 300 KB upload limit. Zones are fractions, so they carry over from the 960 px reference to full-size pipeline stills. The earlier change measured colorful fractions at 960×540 within 0.01 of full size.

**3. Storage per device in the single table.**
- `DOORREF#<device_id>#<created_at>#<rand>` holds `image` (DynamoDB Binary, so 300 KB fits under the 400 KB item limit, unlike base64), `box` (as Decimals), `status` and `created_at`.
- `DOORSETUP#<device_id>` holds `zones` (box, feature, direction, threshold, margin, and the 32×32 baseline as Binary) and `ran_at`.

Adds and deletes update `refs_changed_at` on a small `DOORREFS#<device_id>` marker item, and `stale = refs_changed_at > ran_at`. The pipeline reads only `DOORSETUP#…`, one small `GetItem`. Reference ids in the API are the url-safe base64 of the sort key, like analysis references (`encode_id`/`decode_id`).

**4. Setup algorithm: three features per zone, the best separator wins.**
The owner asked for the check to watch colour, intensity and light changes in their boxes. Each zone measures three values from 0 to 1:
- `color`: the colorful-pixel fraction, unchanged from `door-check-color-zones`.
- `brightness`: mean luminance.
- `change`: mean absolute difference from a 32×32 RGB baseline averaged over the zone's closed references.

For each zone and feature, setup takes the gap between the open and closed reference values in either direction, keeps the feature with the widest gap (at least 0.01), and puts the threshold at the gap's midpoint.
- **Why every feature:** colour is robust to ambient light but misses a greyscale (night/IR) or dark interior. Brightness catches an interior light without colour. Change catches anything that looks different from shut, but also a person standing in front, which the owner's closed references with a person in them will expose as a small margin. Letting the references pick per zone keeps each door on the signal that actually works for it, and the UI shows which one was chosen and its margin.
- **Why 32×32 for change:** it makes the baseline independent of still resolution (960 px references vs full-size pipeline stills) and cheap to store: 3 KB per zone, as Binary in `DOORSETUP#`.
- **Grouping:** boxes are grouped by IoU ≥ 0.3 against each group's bounding box, in creation order, and each reference belongs to its box's zone. Each zone needs its own open and closed references, so a closed drawer reference never decides a door.
- **Ties** go color, change, brightness, the most specific signal first.
- **Considered:** a learned classifier (logistic regression over the three features). Rejected: with a handful of references it overfits, and a single threshold per zone is explainable on screen.

In code, `DoorCheck` gains per-zone rules `ZoneRule(box, feature, direction, threshold, baseline)`. With no setup, the rules are built from `DOOR_ZONES`/`DOOR_THRESHOLD` as `color`/`above`. `door_events.measure(image, box, feature, baseline)` is the one feature function shared by setup and the pipeline.

**5. Pipeline lookup.**
`fetch_stills` gets `setup_for(account_id, device_id) -> DoorCheck | None` (rules from `DOORSETUP#`), built in `handlers/pipeline.py` from `FridgeTable`. If it returns None or raises, the env/default `DoorCheck` is used (`zones_source = "default"`, `door_setup_unavailable` warning on error). Env config is still parsed up front, so invalid `DOOR_ZONES` fails before any Ring call.

**6. Dense sampling with a thread pool.**
`still_times(start, end, count)` already spaces stills evenly, so only `count` changes: `clamp(span // interval, 4, 30)`. Downloads run in a `ThreadPoolExecutor(max_workers=8)`, results sorted by still number. When more than 4 stills are requested, the per-still retry delays drop to 1 s and 2 s, keeping the worst case under 90 s.

**7. Open span, selection and times as pure functions.**
`open_span(scores, threshold)` returns the index range from the first open still through the first still after the last open one. `pick(span, 4)` uses `round(i·(n−1)/3)`. `opened_at` and `closed_at` are the request timestamps of the span's first still and of its closing still (or the window end). Ring does not report a frame's real capture time, so the request time is the best available, about ±1 s at one still per second.

**8. PWA structure.**
- `Config.tsx` becomes a tab shell. The current body moves to `ReferenceImages.tsx`, and a new `DoorDetection.tsx` holds the door tab. Tab state comes from the hash (`#config`, `#config/doors`). `App.tsx` maps any `config…` hash to the Config screen and passes the sub-tab.
- `shapes.ts` (pure): `Shape = {kind: "box" | "line", x1, y1, x2, y2}` in fractions. `dragToShape(kind, start, end)` returns null under 2% for a box. `shapeToBox(shape)` returns `{x, y, width, height}` rounded to 3 places. `clampPoint` keeps points inside the image.
- `ImageMarkup.tsx`: an `<img>` with an SVG overlay and `touch-action: none`. Pointer events become fractions via `getBoundingClientRect`. Props: `tools` (`["box", "line"]` or `["box"]`), `single` (a new shape replaces the old one), `shapes` and `onChange`.
- Flattening: `image.ts` gets `flatten(base64, shapes) -> Promise<string>` (canvas: draw image, stroke red shapes 3 px scaled to size, encode ≤768 px). `ReferenceImages` takes it as an injectable prop next to `resize`, so jsdom tests check the shapes passed instead of pixels.

## Test strategy

- **Unit, backend:**
  - `test_door_calibration.py`: box, status and image validation, the 12-reference limit, add/delete/list on moto DynamoDB, the stale flag, grouping (the IoU example), feature choice (color, brightness, change, direction below, ties), the margin minimum, the 422 failures leaving the setup unchanged, and per-device isolation.
  - `test_camera.py`: the snapshot timestamp, the downscale to 960×540, the ≤300 KB re-encode, blur applied (Rekognition Stubber), 416 twice, Ring 500, refresh failure and Rekognition failure.
- **Unit, backend (`test_still_sampling.py`, `test_door_check.py`):** the count clamp and timestamps, `STILL_INTERVAL_MS` parsing, `open_span`/`pick`, scored times.
- **API (`test_api_door_calibration.py`):** every route through `handlers.api.handler` with the existing token helpers. respx for Ring, Stubber for Rekognition, moto DynamoDB, frozen clock. Covers 401, 403 for viewers with no Ring call, 404 and 409 (no camera found).
- **Task level (`test_fetch_stills_task.py`):** the setup result beats env, the setup threshold applied, the brightness, darker and change rules, the fallback, a raising lookup, per-device isolation, the open-span picks and stored keys, the event times, and the closed-door and too-few-stills cases. Ring is stubbed with respx, keyed by request timestamp.
- **E2E (`test_pipeline_e2e.py`):** existing runs updated to dense sampling. Nova (stubbed Converse) gets the 4 open-span images.
- **PWA (Vitest + Testing Library):**
  - `shapes.test.ts`: the geometry.
  - `ImageMarkup.test.tsx`: drawing, redraw-replaces and undo via pointer events with a mocked 400×225 rect.
  - `ReferenceImages.test.tsx`: today's reference tests moved over, plus snapshot, drawing and the 409.
  - `DoorDetection.test.tsx`: every scenario of the new requirement.
  - `Config.test.tsx`: tabs and the hash.
  - `client.test.ts`: the new methods.
- **Infra:** the API Lambda keeps 20 s, gets `rekognition:DetectFaces` and `DOOR_ZONES`/`DOOR_THRESHOLD`, and stays read-only on secrets; the pipeline Lambda has `STILL_INTERVAL_MS`.
- **Fixtures:** only synthetic JPEGs from `conftest` helpers. No real-camera images are committed. Nothing calls live Ring, AWS or Bedrock.

## Risks / Trade-offs

- [Ring returns the same keyframe for timestamps 1 s apart] → Task 1.1 is a manual spike (with Jayson's OK). If frames repeat, raise the `STILL_INTERVAL_MS` default. Config only; the specs do not change.
- [The owner adds only daytime references, and night openings score differently] → Setup reflects the references given. The UI shows the margin. Night mode stays out of scope.
- [Snapshot fails because nothing moved recently] → A clear 409 message. The owner is usually at the fridge while adding references, which triggers motion.
- [A mislabeled reference produces a bad setup] → A run fails on overlap, so a mislabeled reference usually shows up as "open and closed references overlap" with its score. A new run with corrected references replaces the setup.
- [The API Lambda runs up to about 12 s for a snapshot] → Its existing 20 s timeout covers it. The API stays read-only on secrets, so a snapshot that would need to save a refreshed Ring token answers 502; the token-refresh Lambda (every 3 h, 4 h tokens) keeps that rare.
- [Stored door events change meaning (`duration_s` shorter)] → Stats mixes old and new events for up to 28 days. Accepted for a demo.

## Migration Plan

1. Tests green on `feat/door-zone-setup`, then merge into `local`, then `cdk diff` (API Lambda IAM and env; pipeline env; plus `door-check-color-zones`' env changes), then `cdk deploy` with Jayson's OK.
2. On the phone: Config, then Open/close detection, then add references (doors open and closed, each drawer open), then Run setup. Open each door once and check that `door_event_recorded` has `zones_source = "setup"` and plausible `duration_s`, and that a stored still is cropped.
3. Rollback: redeploy the previous commit. The old code ignores the `DOORREF#`/`DOORSETUP#` items, so no cleanup is needed.
