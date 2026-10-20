# Tasks

Before archiving: archive `door-calibration-from-clips` first, since this change modifies and removes requirements it adds.

## 1. Setup accepts live pictures (backend)

- [x] 1.1 Replace the refusal tests in `backend/tests/test_api_door_calibration.py` with failing tests for "Live zone and references set up" and "Mixed sources"
- [x] 1.2 Drop the live refusal from `door_calibration.run`; verify with `uv run pytest`

## 2. Picture source in the door sheets (PWA)

- [x] 2.1 Write failing tests in `pwa/src/screens/DoorDetection.test.tsx` for "Reference from a live snapshot", "Reference from a recent clip", "Back to live after a clip frame", "Zone drawn on a live snapshot", "Zone redrawn on a clip frame", "Rename keeps the source", "Picker cancelled", "No recent clips", "Camera offline", "Mock video on" and "Open/close detection takes a live frame"
- [x] 2.2 Pass `source` through `api/client.ts`; replace `useClipFrame` with a hook that opens on `cameraSnapshot`, tracks `source`, and offers "New snapshot" and "Recent clip"; verify with `npm test`

## 3. Soft note for live pictures (PWA)

- [x] 3.1 Write failing tests for "Live reference noted" and "Live zone noted"
- [x] 3.2 Replace "Replace with a clip frame" with the soft note and stop live items from disabling Run setup; verify with `npm test`

## 4. Wrap up

- [x] 4.1 Run backend pytest, PWA `npm test`, ruff and `npm run lint`/typecheck green
