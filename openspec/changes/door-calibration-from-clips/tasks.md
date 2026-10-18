# Tasks

Priority if time runs short: groups 1–4 fix detection on their own (strict blue, blue preference, suspect guard). Groups 5–7 (clip-sourced setup) let the owner rebuild a correct setup. Group 8 (mismatch warning) can be cut and moved to a follow-up without touching the others.

Before archiving: archive `door-zones-defined` and `door-auto-calibration` first, since this change adds to the requirements they modify.

## 1. Confirm thresholds on real frames (local only)

- [x] 1.1 Copy the raw debug frames of the 2026-10-17 events into `tmp/door-frames-2026-10-17/` (gitignored, never committed or uploaded; the S3 copies expire around 2026-10-24). Use the profile from `.env` and read-only `aws s3 sync` of `debug/raw-*.jpg`. Verify with `git status` that nothing new is tracked.
- [x] 1.2 With a throwaway scratchpad script, measure the strict blue rule (60/100/120) on zone 1 for: the morning daylight frames, the evening frames of event 1792286435007 (open at frames 18–26), and every `tmp/*.mp4` labelled opening. Confirm closed frames read below 0.01 and open frames at or above 0.01. If not, change the constants and the spec values in this change first. Record the numbers in design.md.

## 2. Strict fridge-light test

- [x] 2.1 Write failing tests in `backend/tests/test_door_check.py` for "Cool daylight on closed doors" and "Weakly blue pixels do not count". Re-run the existing "Fridge light visible", "Faint fridge light counts at the default threshold", "Food in front of closed doors", "Dark colored clothing does not count" and "Stored color setup still works". Confirm the two new tests fail on the 20/60/100 rule.
- [x] 2.2 Add `BLUE_MIN_CHROMA`, `BLUE_MIN_PEAK`, `BLUE_MIN_LEAD` and a blue-only mask in `door_events.py`, leaving `color` on 60/100. Verify with `uv run pytest tests/test_door_check.py` and the door-calibration and self-tuning tests.
- [x] 2.3 Write failing tests in `backend/tests/test_door_calibration.py` for "Daylit steel is not fridge light" and "Fridge interior is fridge light" (reference `blue` values via `GET /api/door-calibration` scores or `measure`). Confirm they pass with 2.2 and fail if the constants are reverted.

## 3. Fridge light preferred in setup and re-tuning

- [x] 3.1 Write failing tests in `test_door_calibration.py` for "Blue wins over a larger change margin", "Blue too close to call" and "Drawer without fridge light". Also re-run the existing "Blue preferred over color on a tie" and "Color chosen when the open reference is not blue".
- [x] 3.2 Factor the feature choice into one `choose_feature` used by `door_calibration.run`, with blue first whenever it separates. Verify that the 3.1 tests and all existing setup tests pass.
- [x] 3.3 Write a failing test in `backend/tests/test_self_tuning.py` for "Re-tune keeps blue". Then make `self_tuning._zone_rule` use `choose_feature`. Verify with `uv run pytest tests/test_self_tuning.py`.

## 4. Clip-wide sanity guard

- [x] 4.1 Write failing unit tests (new `backend/tests/test_suspect_clip.py`) for "Every frame open", "Open at both ends", "Normal opening", "Long opening that starts closed", "Short clip" and "Default rules", on synthetic per-frame results.
- [x] 4.2 Implement `is_suspect(results, zones_source)` in `door_events.py`. Verify the 4.1 tests.
- [x] 4.3 Write failing task-level tests in `backend/tests/test_fetch_stills_clip.py` (synthetic PyAV clip fixture, moto table, stubbed Ring/S3): "Fridge light finds the real opening", "Fridge light finds no opening", "Not suspect keeps the setup result" and the `door_check_suspect` log fields.
- [x] 4.4 Wire the guard into `_fetch_stills`: after alignment, re-score suspect clips with blue rules on the setup zone boxes at `DOOR_THRESHOLD`, set `zones_source = "fallback"` and `suspect = true` in the output. Verify that the 4.3 tests and all existing fetch-stills, clip, trace and follows-camera tests pass.
- [x] 4.5 Write failing tests in `test_self_tuning.py` or `test_fetch_stills_clip.py` for "No sample from a suspect event" and "Normal event still samples". Then skip `_learn` for suspect events. Verify the tests.
- [x] 4.6 Write failing tests in `backend/tests/test_alignment.py` / `test_fetch_stills_clip.py` for "Three suspect events in a row", "Normal event resets the streak", "Setup run resets the streak" and "Streak write fails". Then add `suspect_streak` to the `ALIGN#{device}` item (updated in `_fetch_stills`, zeroed by `alignment.reset`). Verify the tests.

## 5. Zone and reference source (API)

- [x] 5.1 Write failing tests in `backend/tests/test_api_door_calibration.py` for "Reference from a clip", "Source left out", "Unknown source", "Stored before this change", "Rename keeps the source" and "Redraw on a live picture".
- [x] 5.2 Store, validate and return `source` on zones and references in `door_calibration.py` and `handlers/api.py`. Verify with `uv run pytest tests/test_api_door_calibration.py tests/test_door_calibration.py`.

## 6. Setup needs clip pictures

- [ ] 6.1 Write failing tests in `test_api_door_calibration.py` for "Live reference refused", "Live zone refused" and "Everything from clips".
- [ ] 6.2 Make `door_calibration.run` refuse `live` zones (checked first) and references, with the spec's 422 messages and the setup unchanged. Verify the 6.1 tests and the existing setup tests. Update any existing test fixtures to post `source = "clip"` rather than weakening the tests.

## 7. PWA: door setup pictures from recent clips

- [ ] 7.1 Add `source` to the door zone and reference types and to the `api/client.ts` calls (`addDoorZone`, `updateDoorZone`, `addDoorReference`), with a failing client test first.
- [ ] 7.2 Write failing tests in `pwa/src/screens/DoorDetection.test.tsx` for "Reference from a recent clip", "Zone drawn on a clip frame", "Another frame", "No recent clips", "Picker cancelled", "Mock video on" and camera-snapshot's "Open/close detection takes no live frame".
- [ ] 7.3 Replace `useSnapshot` in the Open/close detection sheets with `RecentClipPicker` (or the mock clip picker while "Mock video" is on), rename "New snapshot" to "Another frame", and send `source: "clip"`. Verify with `npm test` in `pwa/`.
- [ ] 7.4 Write failing tests in `DoorDetection.test.tsx` for "Old references marked", "Old zone marked" and "All from clips". Then add the "Replace with a clip frame" notes and the disabled "Run setup" hint. Verify with `npm test`.

## 8. Setup mismatch warning (can be cut)

- [ ] 8.1 Write failing tests in `backend/tests/test_api_warnings.py` for "Three suspect events", "Two suspect events", "Listed last", "Cleared by setup" and "Streak unreadable".
- [ ] 8.2 Add `door_setup_mismatch` to `setup_warnings.warnings_body`, reading `suspect_streak` from the `ALIGN#{device}` item it already reads. Verify the 8.1 tests and the existing warnings tests.
- [ ] 8.3 Write failing tests in `pwa/src/components/Warnings.test.tsx` for "Mismatch banner" and "Viewer sees no link". Then add the code's link in `Warnings.tsx`. Verify with `npm test`.

## 9. Full check

- [ ] 9.1 Run `uv run pytest` and `uv run ruff check .` in `backend/`, and `npm test` and `npm run lint` (if defined) in `pwa/` and `infra/`. All must be green. Report the commands and results.
- [ ] 9.2 Run `uv run python scripts/door_clip_report.py` over the labelled `tmp/` clips and the copied 2026-10-17 frames. Confirm door-check recall is not lower than before the change and that no closed-only event is called an opening. Record the before/after numbers in design.md.
- [ ] 9.3 Add any Ring or AWS friction hit during this change to `docs/friction-log.md`, and add nothing if there was none.
