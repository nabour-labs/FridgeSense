# Proposal

## Why

Tapping "Livestream" while the camera is offline opens a black video box with a countdown. The owner can't tell whether the camera is off or the video is just slow. The app already knows Ring's view of the camera (`GET /api/camera` → `online`), so it can check first and say so plainly.

Tracks: Ring (Partner API devices and live video), Open Source.

## What Changes

- When the Livestream dialog opens, and on "Try again" or "Watch again", the app first asks `GET /api/camera`. If Ring says the camera is offline (`online: false`), the dialog shows "The camera is offline. Check that it's plugged in and connected to Wi-Fi." with "Try again", and no live session is opened.
- If the camera is online, or its status is unknown (Ring unreachable, `online: null`, or the check fails), the live view opens as before.
- Setup snapshots (Reference images "Camera snapshot", Open/close detection and Fridge area) make the same check first. When the camera is offline they show the same offline message and open no live view. They don't fall back to the newest recording either, because it would look current but isn't.
- The video box shows "Connecting…" until the video actually starts playing, instead of a black box. The existing 15 s check still ends a session that never gets video, with "The camera isn't sending video. Check that it's plugged in." That covers the minutes when Ring still reports an unplugged camera as online.

## Out of scope

- The Mock video Livestream and clip picker (they make no camera calls).
- Faster offline detection from Ring webhooks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `camera-live-view`: adds "Online check before a live view" and "No black picture while connecting".
- `camera-snapshot`: adds "Online check before a snapshot".

## Impact

`pwa/src/components/LiveStream.tsx`, `pwa/src/camera/liveSnapshot.ts`, the three setup screens' error handling, and their tests. No backend or infrastructure change: `GET /api/camera` already exists for every signed-in role.
