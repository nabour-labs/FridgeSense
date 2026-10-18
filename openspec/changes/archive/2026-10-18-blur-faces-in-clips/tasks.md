# Tasks

## 0. Prerequisites

- [x] 0.1 Branch `feat/blur-faces-in-clips` off `local`.

## 1. Blur script (clipblur)

- [x] 1.1 Create `clipblur/` with a `pyproject.toml` (Python 3.13; `deface` without its deps, `opencv-python-headless`, `onnxruntime`, `scikit-image`, `numpy`, `av`; pytest in dev) and a test helper that writes synthetic checkerboard clips with PyAV.
- [x] 1.2 Write failing tests for "One face blurred", "Two faces blurred", "Face at the frame edge" and "No faces", using a fake detector. Run them red.
- [x] 1.3 Implement `blur.blur_clip(src, dst, detector)` with PyAV decode/encode and `deface.anonymize_frame`. Verify that 1.2 passes.
- [x] 1.4 Write failing tests for "Face in some frames", "Low score ignored" and "Same timing". Run them red, then make them pass (threshold, downscaled detection with mapped boxes, frame count and rate, `yuv420p`, `+faststart`, no audio).
- [x] 1.5 Write failing tests for "Detector fails" and "Decode error" (the error is raised and no `dst` file is left behind). Make them pass.

## 2. Blur Lambda handler (clipblur)

- [x] 2.1 Write failing moto tests for "Clip published", "Event deleted while blurring" and "Cost logged", plus fail-closed cleanup: when `blur_clip` raises, there's no `clip_key`, the raw clip and any partial clip are deleted, `clip_not_stored` has `reason = "blur_failed"`, and the error is re-raised. Run them red.
- [x] 2.2 Implement `clipblur/handler.py` (S3 get/put/delete, a conditional `UpdateItem`, `clip_blurred` and `clip_blur_cost` logs). Verify that 2.1 passes.
- [x] 2.3 Add `clipblur/Dockerfile` (arm64 Lambda Python 3.13 base). Smoke-test it locally with the runtime emulator on a `tmp/*.mp4` clip (never committed), and record any friction.

## 3. Pipeline stores a raw clip (backend)

- [x] 3.1 In `test_door_events.py`, write failing tests for "Raw clip while blurring is on", "Door opening processed with blurring on" (raw clip present after `FetchStills`), and the raw-upload case of "Upload fails". Keep "Clip cut to the open span", "Door still open at the end of the clip", "Cut fails", "No clip on the fallback path", "Not a door opening", "Door opening processed", and both "Temporary file" scenarios passing. Run them red.
- [x] 3.2 Make `store_open_clip` follow `face_blur`: raw upload with the tag and step output `clip`, or `clip.mp4` as today. Verify that 3.1 passes.
- [x] 3.3 Write failing tests for the `drop_raw_clip` task: it deletes the raw clip, logs `blur_failed`, and tolerates the raw clip already being gone. Implement it in `handlers/pipeline.py`.

## 4. Listing (backend)

- [x] 4.1 Write failing tests for "Viewer gets a blurred clip" and "Clip still being blurred". Keep "Viewer gets no clip", "Recent event with a clip" and the rest of "Door event listing" passing. Run them red.
- [x] 4.2 In `get_events`, return the clip to viewers when `clip_blurred` is true. Verify that 4.1 passes.

## 5. Infrastructure

- [x] 5.1 Write failing CDK assertion tests for "Lifecycle rule synthesized", the `DockerImageFunction` settings and least-privilege role, and the "Blur runs after save", "No raw clip" and "Blur error caught" state transitions. Run them red.
- [x] 5.2 Add the function, the `HasRawClip` choice, `BlurClip`, the `DropRawClip` catch and the tagged lifecycle rule in `door-pipeline.ts`. Verify that 5.1 passes and that `cdk synth` succeeds with Docker running.

## 6. Clip picker (PWA)

- [x] 6.1 Write tests in `RecentClipPicker.test.tsx` for "Only listed clips offered", "Clip being blurred not offered" and "Frame still blurred by the server". Run them. If the existing behaviour already passes, record that, and make sure each scenario is named in a test.

## 7. Docs and checks

- [x] 7.1 Update the README Blur faces and Activity sections: clips are blurred around faces only, best effort, viewers see blurred clips, and Livestream is unchanged.
- [x] 7.2 Run `cd clipblur && uv run pytest && uv run ruff check`, `cd backend && uv run pytest && uv run ruff check`, `cd infra && npm test`, and `cd pwa && npm test && npm run typecheck`, all green, and report the results.
- [x] 7.3 With Jayson's OK, start Docker Desktop, run `cdk diff`, then `cdk deploy`. Open the fridge once with a face in view and check the Activity clip. Add friction-log entries for anything that was surprising.
