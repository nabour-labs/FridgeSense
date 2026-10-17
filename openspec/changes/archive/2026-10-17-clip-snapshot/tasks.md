# Tasks

## 1. Stills bucket CORS (infra)

- [x] 1.1 Write failing CDK assertion tests in `infra/test/pipeline.test.ts` for "CORS rule on the stills bucket" and "Bucket still private". Verify with `cd infra && npm test` that the CORS test fails
- [x] 1.2 Add the CORS rule to the stills bucket in `infra/lib/door-pipeline.ts`. Verify that the 1.1 tests and the rest of `infra` pass

## 2. Shared frame picker (PWA refactor)

- [x] 2.1 Split `FramePicker` (select, video, scrubber, Cancel, "Use this frame", optional `crossOrigin`, `empty` text, `notice`) out of `debug/ClipPicker.tsx`, keeping `ClipPicker`'s behaviour. Verify that `ClipPicker.test.tsx`, `ClipLive.test.tsx` and `DebugBar.test.tsx` pass unchanged

## 3. Recent clip picker (PWA)

- [x] 3.1 Write failing tests in `camera/RecentClipPicker.test.tsx` for "Recent clips listed", "No recent clips", "Recent clip won't load", "Frame can't be grabbed", "Faces can't be blurred" and "Cancel the recent clip picker", plus "Use this frame" sending the grabbed frame to `cameraFrame` and returning the blurred snapshot. Verify that they fail because the module is missing
- [x] 3.2 Implement `RecentClipPicker` on `FramePicker`, using `api.events(7)`, `dayLabel`/`clock` labels, `crossOrigin="anonymous"` and `api.cameraFrame`. Verify that the 3.1 tests pass

## 4. Reference sheet (PWA)

- [x] 4.1 Write a failing test in `Config.test.tsx` for "Add a reference from a recent clip" (the "Recent clip" button, the frame shown for drawing, a 768×432 upload). Verify that it fails
- [x] 4.2 Add the "Recent clip" button and sheet to `AddReference` in `screens/ReferenceImages.tsx`. Verify that the 4.1 test and every existing reference-image test pass

## 5. Wrap up

- [x] 5.1 Run the suites green and report the commands and their results: `cd pwa && npm test && npm run typecheck`, `cd infra && npm test`, and `cd backend && uv run pytest` (nothing changed there, but it confirms the base with `event-open-clip` merged)
- [x] 5.2 Add a friction-log entry if S3 CORS for presigned video or canvas tainting caused friction. Skip it if none did (none: nothing was deployed, so no S3 CORS friction was observed)
