# Proposal

## Why

Config has no place that shows which camera the app is connected to, whether it is online, or what video it delivers. When the fridge stops producing door events, the first question is "is the camera offline?", and today that means opening the Ring app. Ring's Partner API reports device status and capabilities and sends `device_online` / `device_offline` webhooks, so the app can answer this itself. It is also a good Ring Partner API moment for the demo.

Tracks: Ring (Partner API device discovery, status, capabilities, configurations and device webhooks), AWS Builder (Lambda, DynamoDB), Open Source.

## What Changes

- **Webhook:** `device_online` and `device_offline` events are recorded as status changes for the account and device (`STATUS#` items with the event time), after the usual signature check and dedupe. They still always answer 200.
- **API:** `GET /api/camera` returns the account's first camera: its name and product image, the manufacturer ("Ring", since every Partner API device is a Ring device), online now, video capabilities (codecs, aspect ratio, max and supported resolutions), image enhancements (supported, and which are on), motion detection on/off, end-to-end encryption on/off, coarse location, plus the online/offline history of the last 30 days and the uptime over that window. It reads Ring with one call, `GET /v1/devices/{id}?include=status,capabilities,configurations,location`. If the status Ring reports differs from the last recorded one, the change is recorded too, so history keeps working even if a webhook is missed. Every signed-in role can read it.
- **PWA:** a new **Camera** tab, first in Config and the default for `#config` (Reference images moves to `#config/refs`). It shows a status badge (Online / Offline), the camera details in cards, a 30-day online/offline timeline with uptime %, and a **Decoder** card. The Decoder card opens the existing Livestream dialog, reads the browser's WebRTC stats while video plays (codec, decoder implementation, frame size, frames per second) and shows them after the dialog closes.
- **Mock API:** answers `GET /camera` with a canned camera and a few history entries, so the tab can be checked in the browser preview.

Ring reports **no model, manufacturer or firmware field** (a device has only `name` and `image_url`). The page shows the product image, and "Ring" as manufacturer. It does not show a model: Ring's docs say not to infer the model from `image_url`.

## Out of scope

- Model, firmware, serial number, Wi-Fi signal or battery: Ring's Partner API doesn't report them.
- Online/offline history from before this change ships: Ring has no history endpoint for these events, so the timeline starts with the first recorded change.
- Changing camera settings (night vision, HDR, motion zones) from the app; Ring's configurations are read-only for partners.
- More than one camera (the first camera is used, as for snapshots and live view).
- Notifications when the camera goes offline.
- Showing motion or privacy zone polygons.

## Capabilities

### New Capabilities

- `camera-info`: what the app knows about the connected camera (details from Ring, current status, recorded online/offline history and uptime) through `GET /api/camera`, and the Config Camera tab that shows it, including the browser decoder readout.

### Modified Capabilities

- `ring-webhook-intake`: `device_online` and `device_offline` are no longer ignored; they are recorded as status changes.
- `inventory-app`: the "Config screen" requirement now opens on the Camera tab by default (its text still says it has two sub-sections, which is already out of date).

## Impact

- New `backend/src/fridgesense/camera_info.py` (Ring device parsing, status history, uptime); `backend/src/fridgesense/webhook.py` (two event types); `backend/src/fridgesense/handlers/api.py` (one route)
- New fixtures: `backend/tests/fixtures/ring/device_detail.json`, `webhook_device_online.json`, `webhook_device_offline.json`
- `pwa/src/api/client.ts`, `pwa/src/api/types.ts`, new `pwa/src/screens/Camera.tsx`, `pwa/src/screens/Config.tsx` (tab, default, hashes), `pwa/src/components/LiveStream.tsx` (optional stats callback)
- `pwa/scripts/mock-api.ts`
- No infra change: `/api/{proxy+}` already routes to the API Lambda, and the webhook Lambda already writes to the table. Cost: one Ring call and one table query per page open; no S3 or Bedrock use.
- The Ring app's webhook must deliver `device_online` / `device_offline`. If the console needs those event types switched on, that is a manual step.
