# Tasks

Test command for every backend task: `cd backend && uv run pytest -q` (plus `uv run ruff check .`). Infra: `cd infra && npm test`.

## 1. Test helpers

- [x] 1.1 Extend `tests/conftest.py::jpeg` to build an RGB still from a fill colour plus coloured blocks at given fractions, keeping the existing greyscale calls working. Verify with new cases in `test_jpeg_helper.py` (pixel colours at block centres and outside them).
- [x] 1.2 Dropped: Jayson declined committing stills from the recorded clip (2026-10-15). Real-camera tuning moves to the owner-drawn zones in `door-zone-setup`; the colorful-pixel rule stays covered by the synthetic-image scenarios.

## 2. Colorful-pixel, multi-zone door check

- [x] 2.1 Write failing tests for the scenarios "Fridge light visible", "Drawer opening seen only in the drawers zone", "Brightness alone does not count", "Dark colored clothing does not count" and "Threshold is inclusive". Run them and confirm they fail because `DoorCheck` has no zones or colorful-pixel score.
- [x] 2.2 Implement the colorful-pixel fraction and multi-zone `DoorCheck.evaluate` returning (open?, score, zone) so the 2.1 tests pass.
- [x] 2.3 Write failing tests for "Box and threshold from config" and "Invalid zone config" (`DOOR_ZONES` parsing, `;` separator, bounds and arity errors naming `DOOR_ZONES`, defaults `0.38,0.32,0.21,0.30;0.455,0.60,0.12,0.18` and 0.02).
- [x] 2.4 Implement `DoorCheck.from_config(zones, threshold)`, remove the single-box `DEFAULT_BOX` and brightness path, and switch `handlers/pipeline.py` to read `DOOR_ZONES`. Verify that the 2.3 tests and the existing door-check tests (rewritten to the new score) pass.
- [x] 2.5 Dropped with 1.2: the "Recorded clip, doors and drawers" scenario and its test were removed from the spec and the suite.
- [x] 2.6 Write failing tests for "Door stayed closed" and "Closed door costs no face detection" at the `fetch_stills` level: the `motion_not_door` log has `score`, `zone` and `threshold`, the output has `outcome = "not_door"` and `score`, there is no Rekognition call and no S3 object. Implement the renamed fields in `fetch_stills` so they pass, updating `test_fetch_stills_task.py`'s old `brightest` assertion.

## 3. Crop stills to the visible area

- [x] 3.1 Write failing tests for "Crop to the visible strip" (a 2560×1440 still with `0.30,0.0,0.34,1.0` gives 870×1440 starting at x = 768), "No crop configured" (identical bytes) and "Invalid crop config" (errors naming `STILL_CROP`).
- [x] 3.2 Implement crop parsing and a crop step (JPEG quality 95) applied in `fetch_stills` after the door check and before `store_blurred_stills`, and read `STILL_CROP` in `handlers/pipeline.py`. Verify that the 3.1 tests pass.
- [x] 3.3 Write failing tests for "Door check ignores the crop" and the modified "Detection sees the downloaded bytes, S3 sees only the result" (the Rekognition request bytes and the S3 object are the crop when `STILL_CROP` is set). Make them pass.
- [x] 3.4 Update `test_pipeline_e2e.py`: switch the existing runs to `DOOR_ZONES` and colourful stills, and add a run with `STILL_CROP` covering "Analysis sees the cropped still" (the stubbed Converse request's image equals the stored cropped object). Verify that the e2e suite passes.
- [x] 3.5 Check that the unchanged scenarios in the modified requirements still pass: "Four stills saved", "Too few stills", "Too few stills survive face detection", "No face found", "Analysis receives blurred bytes" and "Door check runs on downloaded stills". Update only the fixture stills these tests use (bright to colourful), never their assertions.

## 4. Infrastructure and docs

- [x] 4.1 Write failing assertions in `infra/test/pipeline.test.ts`: the fetch-stills Lambda has `DOOR_ZONES`, `DOOR_THRESHOLD = 0.02` and `STILL_CROP = 0.30,0.0,0.34,1.0`, and no `DOOR_BOX`.
- [x] 4.2 Replace `doorBox` with `doorZones` and add `stillCrop` in `infra/lib/fridgesense-stack.ts` and `infra/lib/door-pipeline.ts`, changing the `doorThreshold` default to 0.02. Verify that `npm test` passes in `infra/` and that `cdk synth` succeeds.
- [x] 4.3 Rewrite the README door-tuning section around `score` and `zone`, `doorZones`, `doorThreshold`, `stillCrop`, and the night-mode limitation. Verify that the documented log query and deploy command match the new field and context names.
- [x] 4.4 If any AWS, CDK or Ring step hit friction, add an entry to `docs/friction-log.md`. If there was none, add nothing.

## 5. Integration check

- [x] 5.1 Run the full suites and linters green: `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`, then `cd infra && npm test`. Report the commands and their results.
- [ ] 5.2 Run `cdk diff` and confirm that only Lambda environment variables change. Then ask Jayson before `cdk deploy`. After the deploy, open the doors, the middle drawer and the bottom drawer once each, and confirm `door_event_recorded` for each one and a cropped stored still.
