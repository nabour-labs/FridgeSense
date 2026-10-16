# Design

## Context

Ring's live video is WHEP: the client POSTs an SDP offer (`application/sdp`) to `/v1/devices/{id}/media/streaming/whep/sessions` with the Ring bearer token, gets the SDP answer in the body and the session URL in `Location`, and DELETEs that URL to end it. Sessions on plug-in cameras last at most 60 s. Ring's sample ([AmazonAppDev/ring-api-helloworld](https://github.com/AmazonAppDev/ring-api-helloworld), `app/api/ring/stream/route.ts` and `app/hooks/useWebRTCStream.ts`) proxies exactly this from a server route.

Today `RingClient._send` builds its own `headers` dict, so callers cannot set `Content-Type`. The app API already has `with_device` (first discovered camera, 409 `no camera found`) and `/api/{proxy+}` routes every `/api/*` path to the API Lambda.

## Goals / Non-Goals

**Goals:**
- Ring token stays server-side; the browser talks WebRTC media directly to Ring.
- The server never follows a URL from the client.
- Every stream the app starts is deleted at Ring when the user stops watching.

**Non-Goals:**
- Lambda relaying media (WebRTC media never touches AWS).
- Retry or reconnect logic beyond the user's "Watch again" / "Try again".

## Decisions

1. **Backend proxy with a session id, not a session URL.** `live.start(ring, device_id, offer) -> (answer, session_id)` and `live.stop(ring, device_id, session_id)` in a new `fridgesense/live.py`. The id is the last path segment of `Location` (relative or absolute). The DELETE route validates the id against `^[A-Za-z0-9._~-]{1,128}$` and rebuilds the path. *Alternative:* return Ring's full URL like the sample does — rejected because the DELETE route would then call a client-chosen URL with our token (SSRF).
2. **`RingClient.request` merges caller headers** under `Authorization` (caller cannot override it). Small, keeps refresh-and-retry-on-401 for free. *Alternative:* raw `httpx` call in `live.py` — would duplicate token refresh.
3. **Routes are not `write=True`.** A live view changes no data, and the user chose to let viewers (judges) watch. The read-only requirement lists its write routes explicitly, so it is unchanged.
4. **Errors map to 502 `camera unavailable`** for any Ring non-2xx, missing `Location`, `httpx.HTTPError` or `RingAuthError`, logged with `log_event("live_failed", status=...)`. Avoids leaking Ring error text and matches the snapshot route. DELETE treats Ring 404 as success.
5. **Offer validation:** string, starts with `v=0`, ≤ 20,000 chars. Real browser offers with gathered candidates are ~3–6 KB; the cap keeps junk out of Ring.
6. **PWA hook `useLiveStream(api, createPeer)`** in `components/LiveStream.tsx`, with a `LiveStream` dialog built on `Sheet`. `createPeer` defaults to `new RTCPeerConnection({iceServers: [stun:stun.l.google.com:19302]})` and is injected in tests. Steps: add `video` and `audio` transceivers `recvonly`, `createOffer`, `setLocalDescription`, wait for ICE gathering complete (max 3 s, as in the sample), POST, `setRemoteDescription`. On `ontrack` set `video.srcObject` and start the countdown from `max_seconds`. A 15 s no-track timer and `connectionstatechange === "failed"` go to the error state. A single `stop()` closes the peer and DELETEs the session once; it runs on close, on unmount, on time-out and on failure. If close happens while the POST is in flight, the late answer's session is deleted right away.
7. **Errors stay in the dialog.** The live calls use the API client without `report`, so the global error notice is not raised.
8. **Video element:** `autoPlay muted playsInline`, 16:9 box, black background, so iOS Safari plays it without a tap.

## Risks / Trade-offs

- [Ring rejects a `recvonly` audio m-line (the sample uses `sendrecv` with no track)] → if the first live test fails with a 400, switch the audio transceiver to `sendrecv` (one-line change) and log it in the friction log.
- [STUN only: strict NAT or corporate networks may not connect] → the 15 s timer shows "Could not connect to the camera."; no TURN for the MVP.
- [Faces are visible in live video, including to viewer/judge tokens] → accepted by Jayson; README notes it.
- [Starting a live view may make the camera record, and a recording near a door opening could look like motion] → only `motion_detected` webhooks start analysis, and live view sends none; check the first real session's webhooks and add a friction-log entry if one arrives.
- [`RingClient` timeout is 5 s; WHEP answer may be slower] → if real calls time out, raise the timeout for the WHEP POST only.
- [A tab killed mid-stream never sends DELETE] → Ring ends the session itself after 60 s.

## Migration Plan

Code only; deploy with the usual `cdk deploy` (with Jayson's OK). Rollback: redeploy the previous version; nothing is stored.

## Test strategy

- **Unit (pytest):** `live.start` / `live.stop` with `respx` mocking `api.amazonvision.com` — exact body, `Content-Type`, bearer token, relative and absolute `Location`, missing `Location`, Ring 4xx/5xx, timeouts, 404 on delete, refresh-and-retry on 401 via `RingClient`.
- **API (pytest):** both routes through `api.handler` with moto Secrets Manager/DynamoDB (`tests/api_helpers.py`), `respx` for Ring: owner and viewer tokens, no token, no camera, bad offer, bad session id. New file `backend/tests/test_api_live.py`.
- **Component (Vitest):** `LiveStream` and the Activity button with a fake peer (records transceivers, `close()` calls, lets the test fire `ontrack` / `connectionstatechange`), a stubbed API client and fake timers for the countdown, 15 s timeout and ICE wait. New file `pwa/src/components/LiveStream.test.tsx`; button tests in `Activity.test.tsx`.
- **Manual:** browser preview against the mock API for the error path; one real live view after deploy (with Jayson's OK), checking webhooks.
- No test calls Ring, AWS or a real WebRTC stack.
