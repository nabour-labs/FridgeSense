# Design

## Context

- Faces are blurred in three places through `faces.FaceBlurrer.blur(jpeg, context) -> bytes | None`:
  - `door_events.store_blurred_stills` (pipeline),
  - `camera.snapshot` and `camera.blur_frame` (the `/api/camera/snapshot` and `/api/camera/frame` routes).
- `None` means detection failed, and every caller fails closed.
- `traces.TraceWriter._door_files` puts each downloaded still as `debug/raw-<n>.jpg`, unchanged, up to `MAX_STILLS = 30` per motion.
- Config items live in the single table under the account's pk, for example `CONFIG#instructions` in `analysis_config.py`.
- The router has `write=True` (refuses the viewer) and `owner=True` (refuses the viewer with `read-only` and the user with `admin only`).
- The Config Camera tab (`screens/Camera.tsx`) is shown to every role, and today it is read-only.
- `infra/lib/fridgesense-stack.ts` reads `context("debugTraces", "true")`.
- Livestream plays Ring's WHEP stream straight in the browser. It stays open to every role and is out of this change.

## Goals / Non-Goals

**Goals:**
- One owner switch, on by default, that controls every face-detection call and what debug traces keep.
- While on, no trace object holds a recognizable face, with no added cost.
- While off, no Rekognition cost.
- Fail toward blurring when the setting can't be read.

**Non-Goals:**
- Livestream blurring or gating.
- Re-processing stills stored while the setting was off.
- A setting per device.

## Decisions

1. **Storage:** item `pk = account pk`, `sk = "CONFIG#face_blur"`, `{enabled: bool, updated_at}`. A missing item means `enabled = true`. New module `fridgesense/face_blur.py`:
   - `load(table, account_id) -> bool` catches `ClientError`/`BotoCoreError`, logs `face_blur_setting_failed` and returns `True`.
   - `save(table, account_id, enabled, now_ms)`.
2. **API:** `GET /api/settings/face-blur` has no flag, so every role can read it. `PUT /api/settings/face-blur` uses `owner=True`. Strict bool check: `type(v) is bool`, so `0` and `"no"` are refused. These are separate routes rather than a field on `GET /api/config`: that route's response shape is spec'd and returns reference images, and the Camera tab shouldn't have to fetch those.
3. **One switch point: a pass-through blurrer.** Add `NoBlur` next to `FaceBlurrer` in `faces.py`, with the same `blur(jpeg, context)` signature. It returns `jpeg` unchanged, calls nothing and logs nothing. A helper `face_blur.blurrer(table, account_id, make_real)` returns `make_real()` when on and `NoBlur()` when off.
   - The pipeline's `_blurrer()` and the two camera routes call this helper, so `store_blurred_stills`, `camera.snapshot` and `camera.blur_frame` don't change.
   - Cropping still happens before `blur`, so off still means cropped.
   - Alternative: an `if enabled` at each call site. Rejected because it touches three bodies and their tests.
4. **The pipeline reads once per motion.** The fetch-stills step loads the setting with the window, uses it for the blurrer, and records `face_blur` in the `DoorTrace`. One read keeps the stored stills and the trace consistent if the owner flips the switch mid-run.
5. **Trace thumbnails:** a pure helper `traces.trace_thumbnail(jpeg) -> bytes | None` downscales to a longest side of 160 px (never upscales), applies `GaussianBlur(2)` and saves as JPEG q80. It returns `None` on a decode error. `_door_files` uses it when `trace.face_blur` is true and stores the raw bytes otherwise. The key name stays `raw-<n>.jpg`, so `door.json`, the API and the Debug view stay as they are.
   - Alternative: Rekognition on each raw still. Rejected for cost (up to $0.03 per motion).
   - Alternative: mask everything outside the door zones. Rejected because the person opening the door stands inside them.
6. **PWA:**
   - `api.faceBlur()` and `api.setFaceBlur(enabled)`.
   - A "Blur faces" section at the bottom of `Camera.tsx`: a `role="switch"` checkbox, enabled only when `isAdmin(role)`.
   - Toggling is optimistic, reverts on error, and hands the error to `report`.
   - It loads on its own, so a slow `GET /api/camera` doesn't hold it up. A failed load shows the switch as on and disabled, which matches the server's fail-on rule.
7. **The CDK default flips to `"false"`.** The code default (on unless `false`) stays, so local and test runs are unchanged.

## Risks / Trade-offs

- **Turning blurring off stores faces for 7 days.** The UI says so. When it's turned back on, older stills aren't re-blurred.
- **Thumbnails are a heuristic.** A face filling most of the frame becomes a 160 px blur blob, which is not identifiable but isn't guaranteed by detection. Traces are owner-only, expire in 7 days, and are now off by default.
- **Livestream stays unblurred for every role.** The user accepted this. The blur text on the Camera tab says so, so the switch doesn't overpromise.
- **Order of archiving.** `camera-snapshot-from-live` must be archived first, or the `camera-snapshot` MODIFIED delta has no base.

## Test strategy

- **Unit (pytest):**
  - `face_blur.load` and `save`: default true, saved false, per account, and a `ClientError` returning true with a warning. Uses moto DynamoDB, plus botocore Stubber for the error.
  - `NoBlur.blur` returns the input bytes.
  - `trace_thumbnail` sizes for landscape, portrait and small inputs. Its output differs from a plain downscale, and garbage bytes give `None`. Images are generated with PIL in the test.
- **Contract (pytest, router):**
  - The `GET` and `PUT /api/settings/face-blur` scenarios for owner, user, viewer and no token, plus bad bodies and per account.
  - Snapshot and frame with the setting off: the Rekognition stub gets no calls.
  - Snapshot with the setting read failing: the stub is called.
  - Ring is stubbed as in `test_api_camera.py` and `test_api_camera_frame.py`.
- **Integration (pytest + moto S3/DynamoDB):**
  - `test_door_events.py`/`test_door_traces.py` with the setting off: stills are stored as downloaded or cropped, there are zero DetectFaces calls and no `face_detect_cost`, and analysis bytes equal the stored objects.
  - `test_traces.py`: thumbnails while on, raw bytes while off, and an undecodable still. The existing assertion that raw objects equal `CLOSED`/`OPEN` moves to the "blurring off" case.
- **Infra (Vitest):** with no context, `DEBUG_TRACES=false`; with `debugTraces=true`, it is `true`.
- **PWA (Vitest + Testing Library, `Camera.test.tsx`):** owner on by default, turning it off sends the `PUT` and shows the notice, a failed save reverts, and user and viewer see it disabled. The API is mocked as in the existing tests.
- Nothing calls Ring, AWS or Bedrock live.
