# Tasks

## 1. Fixtures

- [x] 1.1 Add a `checkerboard_jpeg(size=(320, 180), square=4)` helper to `backend/tests/conftest.py`, and the fixtures `rekognition/detect_faces_one.json` (box `0.40, 0.20, 0.20, 0.30`, confidence 99.1) and `rekognition/detect_faces_two.json` (boxes `0.05, 0.10, 0.15, 0.25` and `0.70, 0.30, 0.15, 0.25`). Extend the fixture-parsing test and verify `cd backend && uv run pytest tests/test_fixtures.py tests/test_jpeg_helper.py` passes

## 2. Blurring face boxes (pure)

- [x] 2.1 Write failing tests in `tests/test_faces.py` for the box math in "One face found" (`0.40, 0.20, 0.20, 0.30` → `0.37, 0.155, 0.26, 0.39`) and "Face at the image edge" (clipped to `0..1`). Verify they fail on the missing `fridgesense.faces`
- [x] 2.2 Implement `enlarge_box` in `backend/src/fridgesense/faces.py` to make the 2.1 tests pass
- [x] 2.3 Write failing tests for `blur_regions` on the checkerboard covering "One face found" (std dev < 10 inside, mean absolute difference ≤ 3 outside), "Two faces found", and "Face at the image edge" (no exception, visible part blurred). Verify they fail
- [x] 2.4 Implement `blur_regions` (pixelate to 8 px on the longer side, Gaussian blur, JPEG q95) to make the 2.3 tests pass, then refactor with tests green

## 3. Face detector and cost log

- [x] 3.1 Write failing Stubber tests for `FaceBlurrer.blur` covering "No face found" (bytes returned unchanged), "One face found" and "Low-confidence face still blurred" (output differs and is blurred), and "Detection sees the downloaded bytes" (expected params `Image={"Bytes": ...}`, `Attributes=["DEFAULT"]`). Verify they fail
- [x] 3.2 Implement `FaceBlurrer` (calls `detect_faces`, blurs every returned box) to make the 3.1 tests pass
- [x] 3.3 Write failing tests covering "Detection fails for one still" (detector part: `ThrottlingException` → `None` and a `face_detect_failed` log with `still` and `error`), "Image rejected by detection" (`InvalidImageFormatException`, `ImageTooLargeException`), a `BotoCoreError` timeout → `None`, and "Failed call is not costed". Verify they fail
- [x] 3.4 Implement fail-closed error handling in `FaceBlurrer` to make the 3.3 tests pass
- [x] 3.5 Write failing `caplog` tests for "Default price" (`usd = 0.001`, `faces = 1`, `still = 3`) and "Configured price" (`0.0008`, `faces = 0`). Verify they fail
- [x] 3.6 Implement the `face_detect_cost` log line to make the 3.5 tests pass. Verify `uv run pytest tests/test_faces.py` passes

## 4. Stills pipeline uses the blurrer

- [x] 4.1 Update `tests/test_stills.py` and `tests/test_fetch_stills_task.py` to pass a pass-through blurrer, and update "Four stills saved" for no faces. Add a failing test that the stored S3 body equals the blurrer's output ("Detection sees the downloaded bytes, S3 sees only the result", storage part). Verify the new test fails
- [x] 4.2 Add the `blurrer` argument to `download_stills` / `fetch_stills` and store only the blurred bytes, to make 4.1 pass
- [x] 4.3 Write failing tests covering "Detection fails for one still" (only still-1, 3 and 4 stored; `still_keys` lists those three), "Detection fails for every still" (no objects, `status = "no_media"`, `still_keys = []`, no analysis), "Too few stills" (blur failure counts), and "Door check runs on blurred stills". Verify they fail
- [x] 4.4 Implement dropping a still when the blurrer returns `None` to make the 4.3 tests pass. Verify `uv run pytest tests/test_stills.py tests/test_fetch_stills_task.py` passes

## 5. Handler wiring and end to end

- [x] 5.1 Write a failing test in `tests/test_pipeline_e2e.py` for "Analysis receives blurred bytes": a Stubber Rekognition reports one face on still 1, and the Converse request's image bytes for still 1 equal the stored object and differ from the download. Verify it fails
- [x] 5.2 Wire up `handlers/pipeline.py` (Rekognition client with 2 max attempts and 5 s/10 s timeouts, and `FaceBlurrer` priced from `FACE_DETECT_PRICE`, default 0.001) to make 5.1 pass
- [x] 5.3 Add the `face_detect_cost` log-tail command to `README.md` next to the Nova one, plus one line about face blurring in the pipeline description. Verify the command matches the log event name in code

## 6. Infrastructure

- [x] 6.1 Write failing tests in `infra/test/pipeline.test.ts`: the pipeline role's only `rekognition:` action is `rekognition:DetectFaces` on `*`, and the function env has `FACE_DETECT_PRICE = "0.001"`. Verify `cd infra && npm test` fails on them
- [x] 6.2 Add the IAM statement and the `faceDetectPrice` context and env to `door-pipeline.ts` / `fridgesense-stack.ts` to make 6.1 pass. Verify `npm test` passes and `npx cdk synth` runs

## 7. Full suite

- [x] 7.1 Run `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check`, plus `cd infra && npm test`. All must be green. Report the commands and results
