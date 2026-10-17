# Tasks

## 1. Monitoring state

- [x] 1.1 Write failing tests in `backend/tests/test_monitoring.py` for "Never paused", "Kept per account and device" and the keep-`since` rule behind "Pause twice" (moto DynamoDB); run `uv run pytest tests/test_monitoring.py` and see them fail on the missing module
- [x] 1.2 Implement `fridgesense/monitoring.py` (`Monitoring`, `load`, `set_paused`, `to_body`) until `uv run pytest tests/test_monitoring.py` passes

## 2. API routes

- [x] 2.1 Write failing tests in `backend/tests/test_api_camera.py` for "Paused camera" and "Ring unreachable" (`monitoring` on `GET /api/camera`); confirm they fail on the missing key
- [x] 2.2 Add `monitoring` to `GET /api/camera` until those tests pass
- [x] 2.3 Write failing tests in `backend/tests/test_api_monitoring.py` for "Pause", "Resume", "Pause twice", "Bad body", "Viewer cannot pause", "User role can pause", "No token" and "No camera"; confirm they fail with 404
- [x] 2.4 Implement `PUT /api/camera/monitoring` in `handlers/api.py` until `uv run pytest tests/test_api_monitoring.py tests/test_api_camera.py` passes

## 3. Webhook gate

- [x] 3.1 Write failing tests in `backend/tests/test_webhook.py` for "Paused camera", "Paused and delivered again", "Active camera", "Paused state unreadable" and "Status events while paused", using the recorded motion fixture and a fake `paused` callable; confirm they fail
- [x] 3.2 Add the `paused` parameter to `handle_webhook` and wire `monitoring.load` in `handlers/http.py` until `uv run pytest tests/test_webhook.py` passes

## 4. Stills-step gate

- [x] 4.1 Write failing tests in `backend/tests/test_fetch_stills_task.py` for "Paused after the run started" (outcome `paused`, no Ring/HTTP/blurrer/table writes) and "Resumed before the stills step"; confirm they fail
- [x] 4.2 Add `paused_for` to `door_events.fetch_stills` and wire it in `handlers/pipeline.py` until `uv run pytest tests/test_fetch_stills_task.py tests/test_fetch_stills_clip.py` passes; update the `fetch_stills` docstring's outcome list

## 5. Paused warning

- [ ] 5.1 Write failing tests in `backend/tests/test_api_warnings.py` for "Paused", "Paused with other problems" and "Active"; confirm they fail
- [ ] 5.2 Add `monitoring_paused` first in `setup_warnings.warnings_body` until `uv run pytest tests/test_api_warnings.py` passes

## 6. PWA

- [ ] 6.1 Add `Monitoring` to `CameraInfo`, the `monitoring_paused` variant to `SetupWarning`, and `setMonitoring(paused)` to `api/client.ts`, with a failing client test in `client.test.ts` that it sends `PUT /api/camera/monitoring` `{"paused": true}`; then make it pass with `npm test -- client`
- [ ] 6.2 Write failing tests in `screens/Camera.test.tsx` for "Active camera", "Pause from the tab", "Resume from the tab", "Change fails" and "Viewer"; confirm they fail
- [ ] 6.3 Implement the FridgeSense card and switch in `screens/Camera.tsx` until `npm test -- Camera` passes; check it at 375 px in the preview in light and dark mode
- [ ] 6.4 Write a failing test in `components/Warnings.test.tsx` for "Banner link", then add the `monitoring_paused` fix link until `npm test -- Warnings` passes

## 7. Docs and full suite

- [ ] 7.1 Add a short "Pausing FridgeSense" note to `README.md` (what it stops, where the switch is)
- [ ] 7.2 Run the full suites and linters green: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`, `cd pwa && npm test && npm run lint` (if defined), `cd infra && npm test`; report the commands and results
