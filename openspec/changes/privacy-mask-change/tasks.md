# Tasks

## 1. Visible map

- [x] 1.1 Write failing tests in `backend/tests/test_alignment.py` for "Map from the newest closed reference", "Overlay text in the mask stays masked" and "Dark but unmasked detail stays visible" (synthetic Pillow images)
- [x] 1.2 Implement `alignment.visible_map(still) -> Image` (80% of 9×9 below gray 16, grown 2 px) with `to_bytes`/`from_bytes` helpers to make the tests pass
- [x] 1.3 Write failing tests in `backend/tests/test_door_calibration.py`: a setup run stores `anchor_visible` (part of "Map from the newest closed reference"), and a failed run leaves it unchanged
- [x] 1.4 Store `anchor_visible` in `door_calibration.run_setup` and add `load_anchor_visible`
- [x] 1.5 Write failing tests for "Setup stored before visible maps" and "No closed reference left for the backfill" (moto table, event through `door_events`)
- [x] 1.6 Implement the lazy backfill in `door_events._follow_plan` / `door_calibration`

## 2. Masked block alignment

- [x] 2.1 Write failing tests for "Wider mask after setup", "Known shift with a mask", "Person in front of the zones in both bookends", "Rotated camera still fails" and "Too little left to compare"
- [x] 2.2 Implement the block match share in `alignment.best_shift` / `align_bookends` (visible maps in, `error = 1 − share`, `ALIGN_MIN_MATCH = 0.5`, block size 8, block limit 0.12, minimum 8 blocks), and update the existing alignment tests only where the spec changed what they assert
- [x] 2.3 Fixture: pull the newest closed reference and the 2026-10-18 21:32Z clip's first and last frames from prod (read-only) and save them at 128×72 grayscale under `backend/tests/fixtures/alignment/mask_change/`. Commit them only after Jayson OKs it; otherwise build a synthetic stand-in
- [x] 2.4 Write failing test "Recorded clip after a mask change" on that fixture, then make it pass (adjust only the constants D2 names, and record the measured shares in the design)
- [x] 2.5 Refactor: keep `_error`'s old callers or remove them, with tests green

## 3. Mask change detection

- [x] 3.1 Write failing tests for "Mask change that misses every zone", "Mask change that covers a zone", "One odd event", "Small difference ignored" and "Mask change while the camera also moved"
- [x] 3.2 Add `mask_streak`, `mask_changed_at` and `mask_zones` to `AlignState`, load and save them (defaults for old items), and implement the check in `alignment.record` (or a sibling called from `align_event`) with the zone boxes passed in
- [x] 3.3 Write failing test "Setup run clears the mask change"
- [x] 3.4 Clear the mask fields in `alignment.reset`

## 4. Warning API

- [x] 4.1 Write failing tests in `backend/tests/test_api_warnings.py` for "One zone covered", "Three zones covered", "Mask change with no zone covered", "Cleared by a setup run" and "Alignment unreadable"
- [x] 4.2 Implement `setup_warnings.privacy_mask_changed` and add it to `warnings_body`

## 5. PWA banner

- [x] 5.1 Write failing tests in `pwa/src/components/Warnings.test.tsx` for "Owner sees the banner and link", "Viewer sees no link" and "No camera-moved banner for a mask change"
- [x] 5.2 Add the `privacy_mask_changed` type in `pwa/src/api/types.ts`, the banner case in `Warnings.tsx`, and a toggle in `pwa/scripts/mock-api.ts`

## 6. Finish

- [x] 6.1 Run `uv run pytest` and `uv run ruff check .` in `backend/`, and `npm test` in `pwa/`; all green
- [x] 6.2 Add a friction-log entry: Ring's device API lists `privacy_zones` but returns no zone shapes, so a mask change had to be inferred from pixels
- [ ] 6.3 After deploy, with Jayson's OK: clear the false move on the prod `ALIGN#` item (`moved = false`, `moved_at = null`, `failures = 0`, `last_moved_at = null`), then confirm `GET /api/warnings` no longer lists `camera_moved`
