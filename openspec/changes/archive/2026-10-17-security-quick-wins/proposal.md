# Proposal

## Why

A codebase review turned up three cheap security fixes worth landing before judging:

- The read-only demo role (`viewer`) can open the live view. Live video goes straight from Ring to the browser and is never face-blurred, so anyone with the demo passcode can watch the kitchen live.
- The handlers log at INFO, and `httpx` logs every request URL at INFO. The pipeline fetches Ring's signed media URLs (they carry `security_token`), so those URLs end up in CloudWatch. Only the assistant module mutes `httpx` today.
- API throttling is per route and shared by every caller. About 15 unsigned requests a second to `POST /ring/webhook` use up its 10 rps limit, so Ring's real deliveries get 429s. After 10 or more failures in a row Ring can disable the webhook.

Tracks: Ring (Partner API webhook, live video), AWS Builder (API Gateway, Lambda logging).

## What Changes

- `POST /api/camera/live` and `DELETE /api/camera/live/{session_id}` refuse the `viewer` role with 403 `{"error": "read-only"}` and don't call Ring. Owner and user keep live view, as they already do for `POST /api/camera/snapshot` and `/frame`.
- The PWA hides the Activity "Livestream" button and the Camera tab's "Decoder" card from viewers.
- Every Lambda handler module sets the `httpx` logger to WARNING, so request URLs are never logged.
- `POST /ring/webhook` gets its own stage limit of 50 requests a second with a burst of 100, so shared junk traffic no longer starves Ring's deliveries.

## Out of scope

- Per-IP rate limits or AWS WAF (HTTP APIs can't attach WAF; it would need CloudFront or a REST API in front).
- Blurring live video.
- Viewer budget for `/api/ask`, CSP headers, account check on webhooks (other review findings).

## Capabilities

### New Capabilities

- `log-hygiene`: HTTP client request URLs are never logged.

### Modified Capabilities

- `camera-live-view`: live view refused for viewers; Livestream button hidden from viewers.
- `camera-info`: Decoder card hidden from viewers.
- `cost-and-abuse-guards`: the webhook route has its own higher limit.

## Impact

`backend/src/fridgesense/handlers/api.py`, `backend/src/fridgesense/logs.py`, `infra/lib/fridgesense-stack.ts`, `pwa/src/screens/Activity.tsx`, `pwa/src/screens/Camera.tsx` and their tests. Needs a `cdk deploy` (backend and stage settings) and a PWA deploy to take effect.
