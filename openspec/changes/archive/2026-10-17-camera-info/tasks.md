# Tasks

## 1. Fixtures

- [x] 1.1 Add `backend/tests/fixtures/ring/device_detail.json` (compound document for "Fridge Cam": status online, capabilities AVC / 16:9 / 1080, enhancements `color_night_vision`, `hdr`, `ir_led_night_vision`, `privacy_zones`, configurations with `hdr: "on"`, motion `"on"`, `e2e_encryption.enabled: false`, and a `locations` resource), plus `webhook_device_online.json` and `webhook_device_offline.json` in Ring's v1.1 shape. Verify `test_fixtures.py` (or a new check there) loads them as valid JSON

## 2. Status history and uptime (backend)

- [x] 2.1 Write failing tests in `tests/test_camera_info.py` for `StatusHistory` on moto: record and list a window newest first, previous status before the window, latest change, and "Other devices and accounts kept apart". Run `uv run pytest tests/test_camera_info.py` and see them fail on the missing module
- [x] 2.2 Implement `StatusHistory` in `backend/src/fridgesense/camera_info.py` (`STATUS#<device_id>#<at_ms>` items) and verify 2.1 passes
- [x] 2.3 Write failing tests for `uptime`: "Uptime over the window", "Short history", "No history", with the spec's exact timestamps
- [x] 2.4 Implement `uptime` and verify 2.3 passes

## 3. Device parsing (backend)

- [x] 3.1 Write failing tests for `parse_device` against `device_detail.json`: "Camera details", "Image enhancements supported and on", "Motion detection and encryption", "Coarse location" (with and without the `locations` resource), and missing `included` resources giving `null` fields
- [x] 3.2 Implement `parse_device` and verify 3.1 passes

## 4. Webhook status events

- [x] 4.1 Write failing tests in `tests/test_webhook.py` for "Device goes offline", "Device comes online", "Repeated status delivery", "Status event without a timestamp" and "Bad signature on a status event", using a fake `StatusRecorder`, plus a test that a recorder error answers 500 and forgets the request id
- [x] 4.2 Add the `StatusRecorder` argument and `device_online`/`device_offline` handling to `handle_webhook`, wire `StatusHistory` in the webhook Lambda entry point, and verify 4.1 and the existing webhook tests pass
- [x] 4.3 Update the `ring-webhook-intake` "Unknown event type" check if it used a status event type, and verify `uv run pytest tests/test_webhook.py` is green

## 5. `GET /api/camera`

- [x] 5.1 Write failing tests in `tests/test_api_camera.py` (Ring via `httpx.MockTransport`, moto table): "Camera details" as a viewer, "No camera linked" (409), "Ring down" (503 → `ring: "unavailable"`), "Ring token rejected", "First read records the status", "Unchanged status is not recorded again", "Missed webhook is caught up", and `history`/`uptime` in the body
- [x] 5.2 Implement the route in `handlers/api.py` with `with_device`, one Ring call with `?include=status,capabilities,configurations,location`, poll-on-read and the unreachable fallback. Verify 5.1 passes
- [x] 5.3 With Jayson's OK, make one read-only live call (`GET /v1/devices/{id}?include=...`) to confirm the single-device route honors `include`. If it doesn't, switch to the list route (design decision 4) and update the fixture to the real shape (with IDs redacted). Log any friction in `docs/friction-log.md`. Verify 3.1 and 5.1 still pass

## 6. PWA: API client and Camera tab

- [x] 6.1 Add `CameraInfo` types and `api.camera()` to `pwa/src/api/types.ts`/`client.ts`, with a failing `client.test.ts` case for `GET /api/camera`, then make it pass
- [x] 6.2 Write failing tests in `pwa/src/screens/Camera.test.tsx` for "Camera tab shows details", "Camera offline", "Ring unreachable", "No camera linked" (no error notice), "History listed" (uptime text, two entries, one offline span) and "Empty history"
- [x] 6.3 Implement `pwa/src/screens/Camera.tsx` (cards in the `configStyles` look, badge, timeline bar, history list) and verify 6.2 passes

## 7. PWA: Config default tab

- [x] 7.1 Update `Config.test.tsx` to the modified "Config screen" scenarios ("Open config" on Camera at `#config`, "Reference images tab" at `#config/refs`, "Direct link to reference images", viewer read-only on Reference images). Run them and see them fail
- [x] 7.2 Add the Camera tab first in `Config.tsx`, move Reference images to `#config/refs`, fit five tabs at 375 px, and verify 7.1 and `App.test.tsx` pass

## 8. PWA: decoder readout

- [x] 8.1 Write failing tests in `LiveStream.test.tsx` for an `onStats` prop: with a fake peer whose `getStats()` returns `inbound-rtp` (video) and `codec` reports, `onStats` gets `{codec: "video/H264", decoder: "ExternalDecoder", width: 1920, height: 1080, fps: 15}` once live (fake timers), and is not called before any track arrives
- [x] 8.2 Implement the stats interval in `useLiveStream` and verify 8.1 and the existing LiveStream tests pass
- [x] 8.3 Write failing Camera tab tests for "Decoder values after a check", "Before any check" and "No video played", then wire the Decoder card to `LiveStream` and verify they pass

## 9. Mock API, docs and checks

- [x] 9.1 Add `GET /camera` to `pwa/scripts/mock-api.ts` (canned details, three history entries, `FRIDGESENSE_MOCK=nocamera` → 409) and check the Camera tab in the browser preview at 375 px and desktop, light and dark
- [x] 9.2 Add one README line on the Camera tab and the online history
- [x] 9.3 Run the full suite and linters green: `cd backend && uv run pytest && uv run ruff check .`, `cd pwa && npm test && npm run lint` (or the repo's lint script), and `openspec validate camera-info`
