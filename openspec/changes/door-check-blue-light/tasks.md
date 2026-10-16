# Tasks

## 1. Baseline

- [ ] 1.1 With the labels confirmed by Jayson (`door-detection-clip-tests` task 5.2) and that change's report available, run `uv run python scripts/door_clip_report.py` and `uv run pytest -m clips` in `backend/` with today's check. Record the confusion matrix, timing errors and failing clips in `design.md` under a "Before" heading.

## 2. The blue feature

- [x] 2.1 Write failing tests in `backend/tests/test_door_check.py` for `measure(..., "blue")`: a `(40,90,200)` block covering 10% gives about 0.10, and the yellow `(220,170,40)` plate, red `(200,40,40)` packet, navy `(20,25,60)` and plain greys `(230,230,230)`/`(30,30,30)` give 0. Run them and see them fail on the unknown feature.
- [x] 2.2 Implement the `blue` feature in `measure` (the existing colourful mask AND `B − max(R,G) > 20`, the threshold as a module constant). Verify that the 2.1 tests pass.

## 3. Default door check

- [x] 3.1 Write failing tests in `backend/tests/test_fetch_stills_task.py` for the scenarios Food in front of closed doors, Faint fridge light counts at the default threshold, and Stored color setup still works. Update the scenarios Drawer opening seen only in the drawers zone, Box and threshold from config, and Threshold is inclusive to the modified spec (blue-lit blocks, feature value). Check that Fridge light visible, Brightness alone does not count, Dark colored clothing does not count, Door stayed closed, Closed door costs no face detection, Fallback when setup never ran, Setup lookup fails and Invalid zone config still hold. Confirm red for the new or changed ones.
- [x] 3.2 Make `blue` the default rule's feature and set `DEFAULT_THRESHOLD` to 0.01. Verify that the 3.1 tests and all door-check, still-sampling and pipeline tests pass.

## 4. Setup chooses blue

- [ ] 4.1 Write failing tests in `backend/tests/test_door_calibration.py` and `test_api_door_calibration.py` for Blue preferred over color on a tie, Color chosen when the open reference is not blue, and the updated Setup from one open and one closed reference (`feature = "blue"`). Check that Brightness chosen when there is no color still holds, and that `defaults` reports `blue` at 0.01. Confirm red.
- [ ] 4.2 Add `blue` first in `FEATURES` (the setup tie order). Verify that the 4.1 tests and the existing setup tests pass.

## 5. Debug traces

- [x] 5.1 Update the default-rule scenario of Deciding rule in the door trace in `backend/tests/test_door_traces.py` (and `test_api_debug.py` if it asserts the feature) to expect `feature = "blue"` with the 0.01 threshold. Confirm red, make it pass, and verify that the setup-rule trace scenario is unchanged.

## 6. PWA and infra

- [ ] 6.1 Write a failing test in `pwa/src/screens/DoorDetection.test.tsx` for Blue light feature named. Then add `"blue"` to `DoorFeature` in `pwa/src/api/types.ts` and the "Blue light" label in `DoorDetection.tsx`. Verify that `npm test` passes in `pwa/`.
- [ ] 6.2 Update `infra/test/stack.test.ts` and `infra/test/pipeline.test.ts` to expect `DOOR_THRESHOLD = "0.01"`, and see them fail. Change the `doorThreshold` context default and its comment in `infra/lib/fridgesense-stack.ts`. Verify that `npm test` passes in `infra/` and that `cdk synth` shows `DOOR_THRESHOLD = 0.01` on both Lambdas.

## 7. Measure and check

- [ ] 7.1 Rerun the report and `pytest -m clips` from 1.1 with the new check. Record the "After" numbers in `design.md` next to "Before". If any clip got worse, stop and discuss before going on.
- [ ] 7.2 Run the full `uv run pytest`, `uv run ruff check . && uv run ruff format --check .` in `backend/`, and `npm test` in `pwa/` and `infra/`. All green.
- [ ] 7.3 Run `cdk diff` and ask Jayson before `cdk deploy`. After the deploy, open the fridge door once and hold a plate of food in front of the closed fridge once. Confirm that the first is a door event with `feature = "blue"` in Config → Debug and the second is `motion_not_door`. Add friction-log entries for anything surprising.
