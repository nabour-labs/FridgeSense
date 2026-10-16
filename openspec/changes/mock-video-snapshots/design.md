# Design

## Context

- **One snapshot seam:** all three setup screens get snapshots only through `api.cameraSnapshot()`. These are `ReferenceImages.tsx` (button), `DoorDetection.tsx` and `FridgeArea.tsx` (when their add or set-area sheet opens, and "New snapshot"). Each resolves to `Snapshot {image: base64 JPEG, captured_at}` and sends any error it doesn't know to `report` from `AppContext`.
- **API wiring:** `App.tsx` builds `api` once, either the injected test fake or a new `ApiClient`, and provides it through `AppContext`.
- **Dev server:** `vite.config.ts` adds the `mockApi()` plugin only when `FRIDGESENSE_MOCK` is set. It proxies `/api` to `FRIDGESENSE_URL` when that is set. `configureServer` middlewares are the existing pattern (`/mock`, `/api` in `scripts/mock-api.ts`).
- **Clips:** `tmp/*.mp4` are 12 H.264 (`avc1`) MP4s of 3.5–25 MB, named `Ring_Fridge_<yyyymmdd>_<hhmm>.mp4`, gitignored. Browsers can play them natively.
- **Backend snapshot size:** `camera.shrink` makes camera snapshots at most 960 px wide (`MAX_WIDTH`). Clip frames match that.

## Goals / Non-Goals

**Goals:**
- One swap point (the `cameraSnapshot` function), so no setup screen changes.
- Zero footprint in the production build: no routes, no bar, no clip code paths reachable.

**Non-Goals:**
- Server-side frame extraction (ffmpeg is not installed and isn't needed).
- Reusing clip frames in tests as fixtures (separate work).

## Decisions

### 1. Debug mode = `import.meta.env.DEV`
- **Choice:** `isDebug()` returns `import.meta.env.DEV`. Vite sets it to true on the dev server and false in `vite build`, and dead-code-eliminates the debug branches in the build.
- **Alternative:** check `location.hostname === "localhost"`. Rejected: `vite preview` of the production build also runs on localhost, and the phone on the LAN reaches the dev server by IP. "Running on the dev server" is what the user means.

### 2. Frames grabbed in the browser, clips streamed by a dev-only plugin
- **Choice:** new `scripts/dev-videos.ts` plugin with `apply: "serve"`, always registered (mock or proxy).
  - `GET /__dev/videos` lists the clips.
  - `GET /__dev/videos/<name>` streams one clip with `fs.createReadStream` and a `Range` → 206 path, so `<video>` can seek.
  - Names are checked against `^[\w.-]+\.mp4$`, with no `..`, and resolved inside the folder before any read.
  - `upload` is `Boolean(process.env.FRIDGESENSE_URL)`.
- **Frame grab:** the picker draws the `<video>` onto a canvas at `fitWithin(w, h, 960)` width and encodes it with `canvas.toBlob("image/jpeg", 0.85)` as base64. The grab is a small injectable function, so tests stub it (jsdom can't decode video).
- **Alternative:** ffmpeg on the dev server, or a new backend route. Rejected: a new dependency, and the backend must never see local clips unless a frame is saved.

### 3. Swap `cameraSnapshot` in `App.tsx` while the switch is on
- **Choice:** `App` keeps `mockVideo` state, read from and written to `localStorage` key `fridgesense.mockVideo` with try/catch. In debug mode with the switch on, it provides `{...api, cameraSnapshot: pickFrame}` through `AppContext`. `pickFrame` opens `ClipPicker` (a `Sheet`) and returns a promise. "Use this frame" resolves it with a `Snapshot`; Cancel or close rejects with `PickCancelled`.
- `report` ignores `PickCancelled`. The screens already send unknown errors to `report` and clear `snapping` in `finally`, so Cancel leaves them unchanged with no edits.
- The API object is a `Pick<ApiClient,…>`. A spread loses the class prototype methods, so the wrapper binds them explicitly with a small `withSnapshot(api, fn)` helper that delegates every other method.
- **Alternative:** a branch inside each screen. Rejected: three edits, three sets of tests, and debug code in production screens.

### 4. Debug bar under the header
- **Choice:** a slim row under the header: a "Debug" label and a "Mock video" switch. It is rendered only when `isDebug()`, for any signed-in role. The header itself stays unchanged so the 375 px layout isn't squeezed.

### 5. Livestream: a clip player in place of the WebRTC view
- **Choice:** a small `DebugContext` provides `{mockVideo}` (default `false` outside the provider, so existing tests are unaffected). `LiveStream` renders `<ClipLive />` instead of running `useLiveStream` when `mockVideo` is true. `ClipLive` is the existing `Sheet` titled "Livestream", with a "Mock video" label, the clip `Select` (reusing the picker's clip list loader) and a `<video autoPlay muted loop playsInline src=…>`.
- **Why:** the swap happens at the dialog, so Activity is unchanged and no WebRTC or `startLive`/`stopLive` calls are made. Branching before the hook keeps hooks order stable: `LiveStream` becomes a thin switch between `ClipLive` and the existing body (moved to `RealLiveStream`).
- **Alternative:** fake an `RTCPeerConnection` whose track comes from `video.captureStream()`. Rejected: it would still call `startLive`, and `captureStream` is uneven across browsers (Safari).

## Risks / Trade-offs

- [Unblurred frames uploaded when proxying to a deployed backend] → Jayson accepted this. The picker shows the notice. Nothing uploads until the owner saves a reference.
- [Opening the add or set-area sheet with the switch on pops the picker straight away] → This is expected, since those sheets take a snapshot when they open. Cancel leaves the sheet with no snapshot and no retry button ("New snapshot" only shows once a snapshot exists), so close the sheet and tap "Add" / "Set area" again. Acceptable for a dev-only tool; the screens are not changed for it.
- [Escape closes both the picker and the sheet under it] → Each `Sheet` listens for Escape on the window. It is harmless (nothing is saved), and a dev-only annoyance.
- [Large clips (25 MB) over the dev server] → Range streaming means only what the scrubber needs is read.
- [Path traversal via the clip name] → Strict name pattern plus a resolved-path check, covered by tests.
- [Debug code leaking into the build] → `apply: "serve"` for the plugin and the `import.meta.env.DEV` guard. Task 5.2 checks the built bundle for `__dev/videos`.

## Migration Plan

Dev-only. Nothing to deploy. Rollback is reverting the branch.

## Test strategy

- **Unit, node environment (`scripts/dev-videos.test.ts`, `// @vitest-environment node`):** run the plugin's middleware against a temp folder (`fs.mkdtemp`) with `a.mp4` (10 bytes), `b.mp4` (20 bytes) and `notes.txt`, using fake `req`/`res`. It covers listing order and shape, the missing folder, `Range` 206, the whole file, path escape, a non-mp4 and an unknown clip giving 404, and `upload` with and without `FRIDGESENSE_URL`.
- **Component (Vitest + Testing Library, jsdom):**
  - `debug/ClipPicker.test.tsx`: `fetch` is stubbed for `/__dev/videos` and the frame grabber is injected. It covers the list order and default selection, "Use this frame" resolving a 960×540 snapshot (the grabber stub returns its size, and the fit math is checked with `fitWithin`), no clips, a clip error (dispatching `error` on the `<video>`), and the upload notice on and off.
  - `debug/ClipLive.test.tsx` and `LiveStream.test.tsx`: under a `DebugContext` with `mockVideo` on, cover "Livestream from a clip" (src, muted, loop, no `startLive`), "Change clip" and "Livestream with no clips". The existing LiveStream tests (no provider) cover "Livestream switch off" unchanged, plus one explicit test with `mockVideo: false`.
  - `debug/mockVideo.test.ts`: the stored switch round trip and throwing storage.
  - `App.test.tsx` / `DebugBar.test.tsx`: `vi.stubEnv("DEV", …)` covers the bar shown and hidden and `/__dev/videos` never fetched when not in debug mode. The switch flows through to the screens: Reference images "Camera snapshot" opens the picker and doesn't call the fake API's `cameraSnapshot`. With the switch off it calls it once. Cancel shows no error and makes no request. Open/close detection "Add" opens the picker.
- **Build check:** `npm run build`, then `grep -r "__dev/videos" dist` finds nothing.
- **Browser preview:** `pwa-mock` with the real `tmp/` clips: pick a frame in each of the three screens, scrub, open Livestream and switch clips, check light and dark at 375 px.
- **Stubbed:** `fetch`, the frame grabber, `localStorage`. No Ring, AWS or Bedrock calls; real clips are used only in the manual preview, never in tests or fixtures.
