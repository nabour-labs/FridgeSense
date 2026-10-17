# Design

## Context

See proposal.md. `openLive` (pwa/src/components/LiveStream.tsx) starts its 15 s timer after `setRemoteDescription` resolves, and clears it in `ontrack`. Browsers fire `track` during `setRemoteDescription`, so the clear runs first and the timer always fires. Measured on the deployed app with the camera unplugged: ICE and DTLS reach `connected`, the answer offers H.264 and Opus, but no RTP arrives (26 transport packets in 24 s, no `inbound-rtp` stats).

## Decisions

1. **Judge "video arrived" by decoded frames from `getStats`** (`inbound-rtp`, `kind: "video"`, `framesDecoded > 0`), polled once a second from when the answer is applied, for up to 15 s. It needs no video element, so the dialog and the snapshot share it inside `openLive`. *Alternative:* `requestVideoFrameCallback` on the dialog's `<video>`. Rejected: the snapshot has its own detached video, and older Safari lacks the callback.
2. **New error message `NO_VIDEO`** reported through `onError`. The snapshot maps it to a `NoVideo` error that the three setup screens show with "Try again". It does not fall back, because the newest recording would look current but isn't.
3. The snapshot's own 15 s frame wait: when the stream has arrived but 10 frames haven't, it is `NoVideo`; before the stream arrives it stays a fallback case.

## Risks / Trade-offs

- [A slow camera wake-up over 15 s reads as "not sending video"] → "Try again" retries; 15 s is the existing limit.

## Test strategy

Vitest only. LiveStream tests: the fake peer reports `framesDecoded` through `getStats` and can fire `track` inside `setRemoteDescription`. Covers "Video never arrives", "Video track arrives before the answer is applied" and "Connection fails". Snapshot tests: "No frames in time" (NoVideo, no fallback) and "Connection fails before any frame" (fallback). One screen test that the NoVideo message and "Try again" show. No Ring or AWS calls.
