# Proposal

## Why

Face blurring is always on and costs a Rekognition call (about $0.001) per stored still, snapshot and live frame. At the same time, debug traces keep every downloaded still unblurred, at full size, for 7 days. The owner should decide whether faces are blurred: on by default for privacy, off when the kitchen has no one to protect and the cost or detail matters more. When blurring is on, it should cover debug traces too.

## What Changes

- **New owner setting "Blur faces", on by default.** It is stored per Ring account. `GET /api/settings/face-blur` returns it for every role. `PUT /api/settings/face-blur` `{"enabled": true|false}` is owner-only: the user gets 403 `admin only` and the viewer gets 403 `read-only`. A missing or unreadable setting counts as on.
- **Config → Camera tab:** the owner gets a "Blur faces" switch. Other roles do not see it.
- **While on (default):**
  - Door-event stills, `POST /api/camera/snapshot` and `POST /api/camera/frame` are blurred as today, and still fail closed.
  - **Debug trace stills change:** `debug/raw-<n>.jpg` becomes a small blurred thumbnail (longest side 160 px) instead of the downloaded bytes. No Rekognition call is added.
- **While off:**
  - No face detection runs anywhere.
  - Door-event stills are stored cropped but not blurred, and are analyzed as stored.
  - Snapshots and frames are returned without blurring.
  - Debug traces store the downloaded bytes, as they do today.
  - No `face_detect_cost` lines are logged.
- **Deploy default:** the CDK context `debugTraces` defaults to `false`. Use `-c debugTraces=true` to turn tracing on for tuning.
- **Livestream is unchanged:** every role, the viewer included, can open it. It has never been blurred, and the setting does not touch it. This accepts that a judge with the demo passcode can watch the kitchen live.

Out of scope:

- Blurring live video.
- Re-blurring stills stored while the setting was off. They expire with the 7-day lifecycle.
- Per-device settings: there is one camera.
- A confirmation dialog when turning blurring off.

Hackathon tracks: AWS Builder (Rekognition, S3 and CDK privacy and cost controls), Ring (owner control over Ring media).

## Capabilities

### New Capabilities

- `face-blur-setting`: the stored on/off setting, its API, its default, who may change it, and the Camera-tab switch.

### Modified Capabilities

- `door-event-detection`: "Faces blurred before storage", "Fail closed when face detection fails" and "Only blurred stills are analyzed" apply only while the setting is on. Debug copies become thumbnails.
- `pipeline-debug-traces`: "Door trace for every motion" stores thumbnails while blurring is on. "Tracing can be turned off" makes off the deployed default.
- `door-calibration`: "Camera snapshot" blurs only while the setting is on.
- `camera-snapshot`: "Blur a live frame" blurs only while the setting is on. This capability comes from `camera-snapshot-from-live`, whose tasks are all done. Archive it before this change.
- `camera-info`: "Camera tab" is no longer read-only for the owner, who gets the switch.

## Impact

- **Backend:**
  - New `fridgesense/face_blur.py`, with load and save for an item `CONFIG#face_blur` under the account.
  - Two routes in `handlers/api.py`, and the snapshot and frame routes read the setting.
  - `door_events.store_blurred_stills` skips detection when the setting is off.
  - `traces.py` writes a thumbnail or the raw bytes depending on the setting.
  - `handlers/pipeline.py` loads the setting once per motion.
- **PWA:** the `api/client.ts` methods `faceBlur` and `setFaceBlur`, and the switch on `screens/Camera.tsx`.
- **Infra:** the `debugTraces` default in `fridgesense-stack.ts`, and its tests.
- **Docs:** README privacy and debug notes, and `docs/submission-checklist.md` items 23–24.
- **Cost:** none added while on. While off, about $0.001 is saved per still, snapshot and frame.
