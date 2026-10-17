# Tasks

Priority if time runs short: groups 1–4 and 6–7 (alignment, moved detection, warnings) are the core. Group 5 (self-tuning) can be cut and moved to a follow-up change without touching the others.

## 1. Measure limits on real clips (local only)

- [x] 1.1 With a throwaway script in the scratchpad (not committed), compute the edge-map alignment error of the `tmp/*.mp4` clips' first and last frames against a closed frame: unshifted, shifted 3 px and 6 px, and a frame with a person. Also compute the zone `change` of open frames against closed ones. Confirm `ALIGN_MAX_ERROR = 0.08` and the 0.08 open-sample limit, or update the numbers in the spec first. Record the measured values in design.md.

## 2. Closed anchor and alignment

- [x] 2.1 Write failing tests in `backend/tests/test_alignment.py` (synthetic test patterns) for "Known shift found", "Better bookend used", "Alignment fails", "Lighting change alone", "Shifted zones" and "Clamped at the edge". Run them and confirm they fail because `alignment` does not exist.
- [x] 2.2 Implement `backend/src/fridgesense/alignment.py` (`edge_map`, `best_shift`, `align_bookends`, `shift_box`) with Pillow only. Verify that the 2.1 tests pass and that one `best_shift` call takes under 300 ms, then refactor with tests green.
- [x] 2.3 Write failing tests (moto DynamoDB) in `test_alignment.py` for "Success resets failures", "Failure counts up", "Three failed alignments", "Large shift", "Stays moved after a good event" and "No anchor" (state unchanged).
- [x] 2.4 Implement the `ALIGN#{device}` state (`load_alignment`, `record_success`, `record_failure`, `reset`) with `moved_at` and `last_moved_at`. Verify that the 2.3 tests pass.
- [x] 2.5 Write failing tests in `test_door_calibration.py` for "Anchor from the newest closed reference", "Failed run keeps the anchor" and "Setup run clears moved" (with `last_moved_at` kept).
- [x] 2.6 Make `door_calibration.run` store `anchor` in the setup item and reset the alignment. Verify that the 2.5 tests and all existing door-calibration tests pass.

## 3. Door check follows the camera

- [x] 3.1 Write failing integration tests in `test_door_events.py`, using a clip encoded with PyAV in a fixture from synthetic frames: "Shifted camera still detects the opening", "Same clip without alignment misses it", "Alignment error does not drop an opening" and "Trace records the shift".
- [x] 3.2 Make `setup_check` take the stored shift and return shifted rules. In `fetch_stills` / `clip_frames_checked`: score with the stored shift, align the first and last frames, re-score the kept frames if the shift changes, and align both bookends first in the stills fallback. Record `alignment` and `rules` in `DoorTrace`. Verify that the 3.1 tests and all existing door-event, clip and trace tests pass.

## 4. Door setup reports alignment

- [x] 4.1 Write failing tests in `test_api_door_calibration.py` for "Reported after an aligned event" and "Before any event" (with `last_moved_at`).
- [x] 4.2 Add `alignment`, `setup.tuned_at` and `setup.tuned_from` to the `GET /api/door-calibration` body. Verify that the 4.1 tests and the existing door-calibration API tests pass.

## 5. Self-tuning from samples (can be cut)

- [x] 5.1 Write failing tests in `backend/tests/test_self_tuning.py` (moto) for "Opening sampled", "Missed opening still sampled", "No clear opening", "Bookend not closed", "Oldest dropped" and "Unaligned event not sampled".
- [x] 5.2 Implement `backend/src/fridgesense/self_tuning.py` (`sample_event`, `store_sample` keeping the newest 20). Verify that the 5.1 tests pass.
- [x] 5.3 Write failing tests for "Tuned rules adopted", "Samples overlap", "Too few samples" and "Re-running setup resets tuning".
- [x] 5.4 Implement `retune` using `door_calibration._choose` and `baseline_of` on owner references plus samples, storing `tuned_zones`, `tuned_at` and `tuned_from`. Make `setup_check` prefer tuned rules, and make `run` delete the samples. Verify that the 5.3 tests pass.
- [x] 5.5 Write a failing test for "Re-tune failure after a claimed opening". Then call sampling and re-tuning after the claim in `fetch_stills` (also for `not_door`), each guarded with a logged warning. Verify that the test and all pipeline tests pass.

## 6. Setup warnings API

- [x] 6.1 Write failing tests in `backend/tests/test_api_warnings.py`, varying the motion setting in the recorded `ring/device_detail.json` fixture, for "All set up", "Several warnings in order", "Motion detection off", "Ring unreachable", "Setup never run", "Setup run", "Both need updating", "Fridge area already updated", "No fridge area", "Setup run but fridge area not updated" and "Both updated".
- [x] 6.2 Implement `backend/src/fridgesense/setup_warnings.py` (`warnings_body`) composing `camera_info.fetch_device`, `load_setup`, the alignment and `fridge_area.load`. Verify that the 6.1 tests pass.
- [x] 6.3 Write failing tests in `test_api_warnings.py` for "No token" and "No camera yet", plus one owner and one viewer read. Add `GET /api/warnings` to `handlers/api.py`. Verify that they pass.

## 7. PWA

- [x] 7.1 Add `warnings()` to `api/client.ts` and the `Warning` / `WarningsBody` types to `api/types.ts`, plus the `alignment` / `tuned_*` fields on the door-calibration body, with failing `client.test.ts` tests first. Verify that they pass.
- [x] 7.2 Write failing tests in `components/Warnings.test.tsx` for "Motion detection off banner", "Setup missing banner", "Camera moved banner with both links", "Camera moved banner with one link", "Viewer sees no links" and "No warnings".
- [x] 7.3 Implement `components/Warnings.tsx`. Verify that the 7.2 tests pass.
- [x] 7.4 Write failing tests in `Fridge.test.tsx` and `Config.test.tsx` for the banner being shown, and "Warnings request fails" (no banner, no error, items shown). Mount `Warnings` in both screens (loaded once per visit, not on the 10 s poll). Verify that the tests pass.
- [x] 7.5 Write failing tests in `DoorDetection.test.tsx` for "Shift and tuning shown", "Moved notice" and "Nothing yet", then add the lines. Verify that they pass.
- [x] 7.6 In the browser preview at 375 px wide, check that the banners fit without horizontal scrolling and that their links open the right tab.

## 8. Docs and checks

- [x] 8.1 Add a short note to the README's Config section on auto-alignment, the warnings and re-running setup after moving the camera. If any AWS or Ring step hit friction, add a `docs/friction-log.md` entry; otherwise add nothing.
- [x] 8.2 Run all suites and linters green: `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`, `cd pwa && npm test && npm run build`, `cd infra && npm test`. Report the commands and their results.
- [ ] 8.3 Run `cdk diff` and ask Jayson before `cdk deploy`. After the deploy: re-run setup on the phone (to store the anchor), open the fridge once and confirm the trace shows `alignment.ok = true`. Turn motion detection off in the Ring app and confirm the banner appears, then turn it back on.
