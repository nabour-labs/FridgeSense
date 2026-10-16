# Tasks

Prerequisite (done 2026-10-15): `door-check-color-zones` is archived and merged into `local`. Work on `feat/door-zone-setup`.

Test commands: backend `cd backend && uv run pytest -q && uv run ruff check .`; PWA `cd pwa && npm test`; infra `cd infra && npm test`.

## 1. Spike: are stills 1 s apart distinct?

- [ ] 1.1 With Jayson's OK (live Ring calls), request 10 stills 1 s apart from one recent motion event through the CLI, and compare their SHA-256 hashes and their mean pixel difference. Record the smallest spacing that gives distinct frames in design.md (Decision 6). If it is not 1000 ms, use it as the `STILL_INTERVAL_MS` default in later tasks. Add a friction-log entry if the Ring media API surprised.

## 2. Dense sampling and open span (backend)

- [x] 2.1 Write failing tests for "One still per second", "Long window capped at 30 stills", "Short window keeps 4 stills" and "Invalid interval config". Run them and confirm they fail because no interval exists.
- [x] 2.2 Implement `still_count` and `parse_interval`, use them in `download_stills`, and read `STILL_INTERVAL_MS` in `handlers/pipeline.py` before any Ring call. Verify that the 2.1 tests pass.
- [x] 2.3 Write failing tests for `open_span` and `pick`: the picks in "Four stills saved" (stills 6, 9, 13, 16), "Short open span" (10, 11) and "Door still open at the end of the window", and None when no still is open.
- [x] 2.4 Implement `open_span` and `pick` as pure functions. Give `DoorCheck` per-zone `ZoneRule`s (feature, direction, threshold, baseline; defaults to `color`/`above` from config) with a shared `measure` for color, brightness and change, and per-still results. Write failing unit tests for `measure` (each feature on synthetic stills) and for the rule directions first. Verify that the 2.3 tests and all existing `test_door_check.py` tests pass, including "Threshold is inclusive" under the per-still meaning.
- [x] 2.5 Write failing task-level tests for "Four stills saved", "Short open span", "Door event saved", "Door still open at the end of the window", "Too few stills keep the window times", "Closed door costs no face detection" (25 stills) and "Too few stills survive face detection" (4 picked).
- [x] 2.6 Make `fetch_stills` store the picked stills as `still-1…4`, take `opened_at`/`closed_at`/`duration_s` from the span, and download in a `ThreadPoolExecutor(max_workers=8)` with 1 s and 2 s retry delays when more than 4 stills are requested. Verify that the 2.5 tests pass along with "Still not ready yet", "Download link gets no token", "Too few stills", "Same Ring event in two runs" and `test_pipeline_e2e.py`.

## 3. Camera snapshot (backend)

- [x] 3.1 Write failing tests in `test_camera.py` for "Snapshot taken" (clock frozen at 2026-10-15T19:20:10Z, Ring timestamp 1792092007000, 960×540, ≤300,000 bytes, nothing stored), "Face blurred in the snapshot", "No recent footage" and "Camera or face detection unavailable" (Ring 500, refresh failure, Rekognition failure).
- [x] 3.2 Implement `backend/src/fridgesense/camera.py` (`snapshot(ring, http, blurrer, device_id, now_ms)`), reusing the still download with attempts and delays as parameters, plus `FaceBlurrer` and a downscale/encode helper. Verify that the 3.1 tests pass.

## 4. Door references and setup (backend)

- [x] 4.1 Write failing tests in `test_door_calibration.py` for reference validation ("Invalid reference rejected"), "Reference limit", add/list/delete on moto DynamoDB ("Reference added", "Reference deleted"), and the stale flag ("Setup marked stale").
- [x] 4.2 Implement references in `backend/src/fridgesense/door_calibration.py` (`DOORREF#`, the `DOORREFS#` marker, Binary image). Verify that the 4.1 tests pass.
- [x] 4.3 Write failing tests for the setup run: "Setup from one open and one closed reference", "Brightness chosen when there is no color", "Change chosen when brightness is the same", "Darker when open", "Overlapping boxes become one zone", "Missing a status", "Open and closed overlap" and "Too many zones" (stored setup unchanged on each failure).
- [x] 4.4 Implement `run` (grouping by IoU, per-zone baselines, the three features through `measure`, best margin ≥ 0.01, midpoint threshold, tie order) and `DOORSETUP#` storage with Binary baselines. Verify that the 4.3 tests pass.
- [x] 4.5 Write failing task-level tests for "Setup result used for the device", "Setup threshold applied", "Brightness rule applied", "Darker rule applied", "Change rule applied", "Fallback when setup never ran", "Setup lookup fails", "Setup kept per device", "Box and threshold from config", "Door stayed closed" (with `zones_source`) and "Invalid zone config".
- [x] 4.6 Add the `setup_for` lookup to `fetch_stills` and `handlers/pipeline.py`, and log `zones_source`, `feature` and the threshold used in `motion_not_door` and `door_event_recorded`. Verify that the 4.5 tests pass.

## 5. API routes (backend)

- [x] 5.1 Write failing API tests for `POST /api/camera/snapshot` (200, 409 no recent footage, 502), "No device discovered" on every route, "Nothing set up yet", "No token" and "Viewer cannot change the setup" (no Ring request).
- [x] 5.2 Write failing API tests for the reference and run routes end to end: add (200, 400s, 409 limit), delete (200, 404), run (200, the three 422s with `references` in the body).
- [x] 5.3 Implement the five routes in `handlers/api.py`, with defaults from `DOOR_ZONES`/`DOOR_THRESHOLD`. Verify that the 5.1 and 5.2 tests pass, then refactor with tests green.

## 6. PWA

- [ ] 6.1 Add `cameraSnapshot`, `doorCalibration`, `addDoorReference`, `deleteDoorReference` and `runDoorSetup` to `api/client.ts` and the types to `api/types.ts`, with failing tests in `client.test.ts` for each method, path and body first. Verify that they pass.
- [ ] 6.2 Write failing tests in `shapes.test.ts` (dragging out a box and a line, the 2% minimum, clamping, `shapeToBox` rounding to 3 places), then implement `pwa/src/shapes.ts`. Verify that they pass.
- [ ] 6.3 Write failing tests in `ImageMarkup.test.tsx` (draw a box, draw a line, `single` redraw replaces, tiny drag ignored, read-only ignores drags) with a mocked 400×225 rect, then implement `ImageMarkup.tsx`. Verify that they pass.
- [ ] 6.4 Write failing tests for the Config tabs: "Open config", "Switch to open/close detection", "Open the detection tab by link" and "Viewer sees read-only config". Split `Config.tsx` into a tab shell plus `ReferenceImages.tsx`, and map `#config/doors` in `App.tsx`. Verify that the new tests pass and that all existing Config tests pass unchanged against `ReferenceImages`.
- [ ] 6.5 Write failing tests for "Add a camera snapshot", "Snapshot with no recent footage", "Draw on the image", "Undo a shape" and "Add a reference" (with the injected `flatten`), then add the two sources, the drawing tools and `flatten` in `image.ts`. Verify that the tests pass along with "Annotation required", "Limit reached", "Delete a reference" and "Upload refused".
- [ ] 6.6 Write failing tests in `DoorDetection.test.tsx` for every scenario of "Open/close detection tab", then implement `DoorDetection.tsx`. Verify that `npm test` passes in `pwa/`.

## 7. Infrastructure and docs

- [ ] 7.1 Write failing assertions in `infra/test`: the API Lambda has a 25 s timeout, `rekognition:DetectFaces` and `DOOR_ZONES`/`DOOR_THRESHOLD`; the fetch-stills Lambda has `STILL_INTERVAL_MS` (the value from 1.1).
- [ ] 7.2 Update `infra/lib/fridgesense-stack.ts` and `infra/lib/door-pipeline.ts` to match. Verify that `npm test` passes in `infra/` and `cdk synth` succeeds.
- [ ] 7.3 Update the README door-tuning section: Config → Open/close detection, Run setup, `zones_source`, `STILL_INTERVAL_MS`, and the new meaning of `duration_s`. Check that the names match the logs and the API.
- [ ] 7.4 If any AWS, CDK or Ring step hit friction, add an entry to `docs/friction-log.md`. If there was none, add nothing.

## 8. Integration check

- [ ] 8.1 Run all suites and linters green: `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`, `cd pwa && npm test && npm run build`, `cd infra && npm test`. Report the commands and their results.
- [ ] 8.2 Run `cdk diff` and ask Jayson before `cdk deploy` (this deploy also ships `door-check-color-zones`). After the deploy: add door references on the phone, run setup, open each door and drawer once, and confirm `door_event_recorded` with `zones_source = "setup"`, a plausible `duration_s` and a cropped stored still.
