# Tasks

## 0. Prerequisites

- [x] 0.1 Archive `camera-snapshot-from-live` (all tasks done) so `openspec/specs/camera-snapshot` exists. Then branch `feat/face-blur-setting` off `local` after that branch is merged.

## 1. Stored setting (backend)

- [x] 1.1 Write failing tests in `backend/tests/test_face_blur.py` (moto DynamoDB) for `face_blur.load` and `save`: default true ("Default is on"), saved false ("Saved off"), "Kept per account", and "Unreadable setting counts as on" (a Stubber `ProvisionedThroughputExceededException` gives true plus a `face_blur_setting_failed` warning). Also test `faces.NoBlur.blur` returning its input.
- [x] 1.2 Implement `fridgesense/face_blur.py` (`load`, `save`, `blurrer`) and `faces.NoBlur`. Verify that 1.1 passes.

## 2. Setting API (backend)

- [x] 2.1 Write failing tests in `backend/tests/test_api_face_blur.py` for every scenario of "Read the face-blur setting" and "Change the face-blur setting": owner off and on again, user 403 `admin only`, viewer 403 `read-only`, bad bodies 400, no token 401, per account, and the `face_blur_changed` log line.
- [x] 2.2 Add the `GET`/`PUT /api/settings/face-blur` routes in `handlers/api.py`. Verify that 2.1 passes.

## 3. Snapshot and frame follow the setting (backend)

- [x] 3.1 Write failing tests in `test_api_camera.py` and `test_api_camera_frame.py`: "Snapshot while blurring is off" and "Frame while blurring is off" (zero DetectFaces calls, 960×540 result), and "Read fails for a snapshot" (detection is called). Keep "Snapshot taken", "Face blurred in the snapshot", "Snapshot from the latest motion event", "No recent footage", "Camera or face detection unavailable", "No device discovered", "Frame blurred and returned", "Face blurred in the frame", "Small frame kept at its size" and "Face detection unavailable" passing.
- [x] 3.2 Have both routes get their blurrer from `face_blur.blurrer(ctx.table, ctx.account_id, …)`. Verify that 3.1 passes.

## 4. Pipeline follows the setting (backend)

- [x] 4.1 Write failing moto tests in `backend/tests/test_door_events.py` for "Blurring off, no crop box", "Blurring off, with a crop box", "Analysis while blurring is off" and "Read fails in the pipeline". Re-run the existing "One face found", "Two faces found", "Low-confidence face still blurred", "Face at the image edge", "No face found", "Detection sees the downloaded bytes, S3 sees only the result", "Detection fails for one still", "Detection fails for every still", "Image rejected by detection", "Analysis receives blurred bytes" and "Door check runs on downloaded stills" unchanged.
- [x] 4.2 In `handlers/pipeline.py`, load the setting once per motion in the fetch-stills step, build the blurrer from it, and set `DoorTrace.face_blur`. Verify that 4.1 passes.

## 5. Debug trace stills (backend)

- [x] 5.1 Write failing unit tests for `traces.trace_thumbnail`: "Raw stills are small blurred thumbnails" (1920×1080 gives 160×90 and differs from a plain downscale), "Portrait still", "Small still not upscaled", and garbage bytes giving `None`.
- [x] 5.2 Implement `trace_thumbnail`. Verify that 5.1 passes.
- [x] 5.3 Write failing moto tests in `test_traces.py`/`test_door_traces.py`:
  - "Still that cannot be decoded".
  - "Raw stills are the downloaded bytes": move the existing assertion that raw equals `[CLOSED, OPEN, OPEN, CLOSED]` here.
  - With blurring on, no trace object equals the downloaded bytes.
  - "Debug copy is not an event still".
  - "No debug stills when tracing is off".
  - Keep "Motion that is not the door", "Door opening", "Too few stills", "Duplicate run" and "Off" passing.
- [x] 5.4 In `TraceWriter._door_files`, thumbnail stills when `trace.face_blur` is true, and write `key = null` for `None`. Verify that 5.3 passes along with the whole of `test_traces.py` and `test_door_traces.py`.

## 6. Tracing off by default when deployed (infra)

- [x] 6.1 Write failing Vitest tests in `infra/test/pipeline.test.ts`/`stack.test.ts`: "Off by default when deployed" and "Turned on for tuning". Update the existing default `toBe("true")` assertion.
- [x] 6.2 Change the `debugTraces` context default to `"false"` in `fridgesense-stack.ts` and update its comment. Verify that 6.1 passes.

## 7. Blur faces switch (PWA)

- [x] 7.1 Write failing tests in `pwa/src/api/client.test.ts` for `faceBlur()` (`GET`) and `setFaceBlur(false)` (`PUT` with `{"enabled": false}`).
- [x] 7.2 Implement the client methods and add them to the `Api` type and the `test-utils` mock. Verify that 7.1 passes.
- [x] 7.3 Write failing tests in `pwa/src/screens/Camera.test.tsx`: "Owner sees it on by default", "Owner turns it off", "Save fails" and "Others see it read-only" (user and viewer). Add "Only the blur switch is editable", and keep "Camera tab shows details", "Camera offline", "Ring unreachable" and "No camera linked" passing.
- [x] 7.4 Add the "Blur faces" section to `Camera.tsx`. Verify that 7.3 passes.

## 8. Docs and wrap-up

- [x] 8.1 Update the README privacy and debug notes (the switch, the default on, thumbnails, `-c debugTraces=true`). Tick items 23–24 in `docs/submission-checklist.md`, noting that Livestream stays open to the viewer by choice.
- [x] 8.2 Run the full suites green: `cd backend && uv run pytest && uv run ruff check .`, `cd pwa && npm test`, `cd infra && npm test`. Report the commands and results.
- [ ] 8.3 With Jayson's OK, run `cdk diff` and then `cdk deploy`. Toggle the switch as the owner, open the fridge once with it on, and confirm the stored stills are blurred. Add friction-log entries for anything surprising.
