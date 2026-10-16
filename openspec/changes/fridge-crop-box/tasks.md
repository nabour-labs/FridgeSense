# Tasks

## 1. Store the fridge area

- [x] 1.1 Write failing tests in `backend/tests/test_fridge_area.py` (moto DynamoDB) for saving and loading an area, "Saving again replaces the area", "Invalid fridge area rejected" (stored area unchanged) and "Fridge area kept per device". Run them and confirm they fail because `fridge_area` does not exist.
- [x] 1.2 Implement `backend/src/fridgesense/fridge_area.py` (`FridgeArea`, `save`, `load`, `FRIDGEAREA#<device_id>`), reusing `door_calibration.decode_image` and `validate_box`. Verify that the 1.1 tests pass.

## 2. API routes

- [x] 2.1 Write failing tests in `backend/tests/test_api_fridge_area.py` for "No fridge area yet", "Viewer reads the fridge area", "Fridge area needs a camera", "Fridge area needs a token", "Fridge area saved" (clock frozen at 2026-10-16T01:00:00Z), "Saving again replaces the area", "Invalid fridge area rejected" and "Viewer cannot save the fridge area".
- [x] 2.2 Add `GET /api/fridge-area` and `PUT /api/fridge-area` (write) to `handlers/api.py` with `with_device`. Verify that the 2.1 tests pass, then refactor with tests green.

## 3. PWA

- [x] 3.1 Add `fridgeArea()` and `saveFridgeArea(image, box)` to `api/client.ts` and the `FridgeAreaBody` type to `api/types.ts`, with failing tests in `client.test.ts` for each method, path and body first. Verify that they pass.
- [x] 3.2 Write failing tests in `Config.test.tsx` for "Switch to fridge area" and "Open the fridge area tab by link". Add the third tab to `Config.tsx` (`grid-cols-3`, labels that may wrap) and map `#config/fridge` in `App.tsx`. Verify that the new tests and all existing Config and DoorDetection tests pass unchanged.
- [x] 3.3 Write failing tests in `screens/FridgeArea.test.tsx` for "Fridge area shown", "No fridge area", "Set the fridge area", "Box required to save", "Redraw replaces the fridge box", "Cancel setting the area", "Snapshot fails while setting the area" and "Viewer sees the fridge area read-only".
- [x] 3.4 Implement `screens/FridgeArea.tsx` with `ImageMarkup` (single box), the snapshot sheet and `NO_FOOTAGE` handling. Verify that the 3.3 tests pass and that `npm test` passes in `pwa/`.
- [x] 3.5 In the browser preview at 375 px wide, check that the three tabs fit without horizontal scrolling, and that drawing and saving a box works against the dev API mock or demo mode.

## 4. Docs and checks

- [x] 4.1 Add a short "Fridge area" note to the README's Config section (where it is set, that nothing uses it yet). If any AWS step hit friction, add a `docs/friction-log.md` entry; otherwise add nothing.
- [x] 4.2 Run all suites and linters green: `cd backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`, `cd pwa && npm test && npm run build`, `cd infra && npm test`. Report the commands and their results.
- [ ] 4.3 Run `cdk diff` and ask Jayson before `cdk deploy` (only the API Lambda code and the site change). After the deploy: set the fridge area on the phone and confirm `GET /api/fridge-area` returns it.
