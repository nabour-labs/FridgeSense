# Design

## Context

- Devices are discovered after linking and stored as `DEVICE#<id>` items (name only) under `ACCOUNT#<account_id>`. API routes that need a camera use `with_device`, which picks the first stored device and answers 409 when there is none.
- The webhook Lambda verifies, dedupes and dispatches `motion_detected`; every other type is logged as ignored and answered 200.
- Ring's device resource has only `name` and `image_url`. Status, capabilities, configurations and location come as JSON:API `included` resources when asked for with `?include=` (shapes as in Ring's Device Discovery, Capabilities, Configurations and Status docs).
- Config's tabs live in `pwa/src/screens/Config.tsx`, driven by the location hash. `refs` is the default today.
- The Livestream dialog (`LiveStream.tsx`) owns its `RTCPeerConnection` inside `useLiveStream`.

## Goals / Non-Goals

**Goals:** one Ring call per page open; history that survives a missed webhook; no new infra.

**Non-Goals:** background polling of camera status; a separate status table or GSI; reading decoder stats outside the existing Livestream dialog.

## Decisions

1. **Status changes as items in the single table.** `pk = ACCOUNT#<account_id>`, `sk = STATUS#<device_id>#<at_ms zero-padded to 13 digits>`, attributes `online`, `at_ms`, `source` (`webhook` | `poll`). A `begins_with` / `between` query on `STATUS#<device_id>#` gets the window, and one more query (`ScanIndexForward=False`, `Limit=1`, `sk < STATUS#<device_id>#<window start>`) gets the status before the window. No TTL: a few items per month. *Alternative:* a TTL'd item per day with a running state, rejected as more code for no gain at this size.

2. **Record on read, too.** Ring may not deliver `device_online`/`device_offline` to this app (see Open Questions), and the docs list them inconsistently. Writing a `poll` change whenever Ring's `online` differs from the newest recorded one keeps the timeline honest with or without webhooks. Webhook changes keep Ring's own timestamp, so they are more precise. A late webhook with an older timestamp lands in time order and does not affect the newest-status comparison, which uses the newest `at_ms`.

3. **New module `camera_info.py`.** Pure functions: `parse_device(json) -> CameraDetails` (merges `included` by type+id; an enhancement is listed when capabilities support it and configurations give it an `"on"`/`"off"` string, since the live camera also lists `snapshot` and configures settings it doesn't support, `e2e_encryption.enabled` is a boolean), `uptime(changes, before, now, window_days=30)`, plus a small `StatusHistory` repository (record, list window, latest). The API route wires them with `RingClient` and the stored device. Keeps `handlers/api.py` thin, like `door_calibration.py`.

4. **One Ring call:** `GET /v1/devices/{id}?include=status,capabilities,configurations,location`. Ring documents `include` on the list route only. A live call on 2026-10-16 confirmed the single-device route honors it too, with the same compound document; the parser also accepts the list shape (`data` as an array) and picks the device by id.

5. **Manufacturer is a constant "Ring"; no model.** Ring's docs say not to infer the hardware from `image_url`. The product image itself shows which camera it is.

6. **Webhook dispatch.** `handle_webhook` gets a `StatusRecorder` protocol argument, like `MotionHandler`. `device_online`/`device_offline` parse `attributes.source` and `attributes.timestamp` and call it. A missing field is logged as `webhook_malformed` and answered 200. A table error answers 500 after `log.forget`, the same as a failed motion hand-over, so Ring retries.

7. **Decoder readout via an `onStats` prop on `LiveStream`.** `useLiveStream` exposes its peer. While `state.kind === "live"`, an interval calls `peer.getStats()` every 1 s, finds the `inbound-rtp` report with `kind === "video"`, and resolves its `codecId` to the `codec` report's `mimeType`. It passes `{codec, decoder: decoderImplementation, width: frameWidth, height: frameHeight, fps: framesPerSecond}` to `onStats`. The Camera tab keeps the last value in state and shows it once the dialog closes. Nothing is stored server side. The Mock video clip player (`ClipLive`) reports nothing, which is fine: it is a dev tool.

8. **Tab and hash.** `SECTIONS` gets `{id: "camera", label: "Camera", hash: "#config"}` first, and `refs` moves to `#config/refs`. Five tabs for the owner and four for others, so the grid goes to `grid-cols-5`/`grid-cols-4` with smaller labels on phones. A flex row that scrolls sideways is the fallback if five don't fit at 375 px.

9. **Timeline bar.** A plain `div` of absolutely positioned spans (left/width as % of the 30-day window), green for online and slate for offline, with a gray span for the time before `uptime.since`. No Recharts needed.

## Risks / Trade-offs

- [Ring never sends device online/offline webhooks to this app] → poll-on-read still records changes whenever the tab is opened. The history is then coarser (time of the read, not of the change), and the source is shown per entry.
- [Uptime is wrong if the camera changed state twice between reads with no webhooks] → accepted. The page states the window and the start of known history (`since`).
- [`include=configurations` or `location` missing on some devices] → each field falls back to `null` and shows as "Not reported".
- [Five tabs crowd a phone screen] → shorter labels at small widths ("Refs", "Doors"), checked at 375 px in the preview.
- [`getStats` field names differ by browser (Safari leaves out `decoderImplementation`)] → missing fields show "Not reported".

## Migration Plan

Deploy the backend (webhook and API Lambdas) and then the PWA. No data migration: history starts empty and the first page open records the current status. Rollback is a redeploy of the previous version; the leftover `STATUS#` items are harmless.

## Open Questions

- Does the Ring developer console need `device_online`/`device_offline` switched on for the webhook? To check in the console after deploy. It changes no code, because poll-on-read covers it either way.

## Test strategy

- **Unit (pytest):** `parse_device` against `tests/fixtures/ring/device_detail.json` (a recorded-shape compound document built from Ring's documented examples, until a live response is captured), including missing `included` resources. `uptime` with the spec's exact timestamps. `StatusHistory` on moto DynamoDB: record, window query, previous-status query, account and device isolation.
- **Contract (pytest):** the API route through `handler()` with Ring stubbed by `httpx.MockTransport`: 200 shape, viewer access, 409 with no device, Ring 503 and auth error → `ring: "unavailable"`, poll-on-read writes. The webhook through `handle_webhook` with the new `webhook_device_online.json`/`webhook_device_offline.json` fixtures, signed in the test: stored change, duplicate, missing timestamp, bad signature.
- **Component (Vitest + Testing Library):** `Camera.tsx` with `fakeApi`: details, badges, unreachable message, 409 text, history list, empty history, uptime text, timeline spans. `Config.tsx` tab default and hashes (update the existing tests that expect Reference images at `#config`). `LiveStream` `onStats` with a fake peer whose `getStats` returns a `Map` of `inbound-rtp` and `codec` reports, using fake timers.
- **Stubbed:** Ring (MockTransport), DynamoDB (moto), WebRTC (fake `RTCPeerConnection`). Nothing calls live Ring or AWS.
- **Manual:** the mock API preview at 375 px and desktop, light and dark.
