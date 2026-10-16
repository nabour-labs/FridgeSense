# Tasks

## 1. Wide Livestream dialog

- [x] 1.1 Write failing tests: "Livestream dialog is wide" in `pwa/src/components/LiveStream.test.tsx`, "Mock video Livestream is wide" in `pwa/src/debug/ClipLive.test.tsx`, and "Other dialogs keep their width" in a new `pwa/src/components/Sheet.test.tsx`. Run `npm test` and see the two wide tests fail.
- [x] 1.2 Add `size` to `Sheet` and pass `size="wide"` from `RealLiveStream` and `ClipLive`. Verify `npm test` passes.
- [x] 1.3 In the browser preview with Mock video on, open Livestream at desktop width and confirm the video is about 720 px wide; at phone width it is a full-width bottom sheet.
