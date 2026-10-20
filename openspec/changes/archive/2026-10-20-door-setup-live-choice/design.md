# Design

## Context

The door sheets use `useClipFrame` in `DoorDetection.tsx`. It opens `RecentClipPicker` on mount, and cancelling before any frame closes the sheet. The Fridge area sheet calls `api.cameraSnapshot` on mount (a live frame, falling back to the Ring still, blurred via `/api/camera/frame`) and offers "New snapshot". Backend `door_calibration.run` raises `SetupFailed` for any `source != "clip"`.

## Decisions

### 1. Open on a live snapshot, like Fridge area
The owner asked for the Fridge area flow. The sheet calls `cameraSnapshot` on mount. "New snapshot" repeats it, and "Recent clip" opens the picker. Both buttons also sit next to the error, so a camera that is offline still leaves the clip route open ("Try again" stays for the live route).

### 2. Source follows the shown picture
The hook keeps `source` next to `snap`. A live snapshot sets `"live"`, and a picked clip frame sets `"clip"`. With "Mock video" on, `cameraSnapshot` already returns a mock *clip* frame, so the live route sets `"clip"` there, as today.

### 3. The caller passes `source` to the client
`addDoorZone(name, box, source)`, `updateDoorZone(id, {name?, box?, source?})` and `addDoorReference(image, zoneId, status, source)`. The client no longer hard-codes `"clip"`.

### 4. Remove the setup refusal, keep `source`
Live pictures are still framed differently. The stored `source` drives the soft note, and the existing suspect guard and mismatch warning still catch the effect. No data migration.

## Risks

- Live-drawn setups may cause false openings again. They are mitigated by the suspect guard (fridge-light fallback) and by the mismatch banner, and the note tells the owner why.

## Test strategy

- **Unit / API (pytest + moto, `test_api_door_calibration.py`):** setup with a live zone and live references answers 200 and stores rules. The old refusal tests are removed along with their requirement.
- **PWA (Vitest + Testing Library, `api` doubles as in `DoorDetection.test.tsx`):** the sheet takes a live snapshot on open and sends `source = "live"`. "Recent clip" opens the picker, and the frame it returns is sent with `source = "clip"`. Cancelling the picker keeps the sheet. "New snapshot" after a clip frame sends `"live"`. Mock video sends `"clip"`. A zone redrawn live sends `source = "live"`. The soft note shows, and Run setup is enabled with live items. Offline camera shows the error with Try again and Recent clip.
- No live Ring, AWS or Bedrock calls.
