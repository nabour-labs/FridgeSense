# Design

## Context

`door-zone-setup` already provides everything this tab needs except storage: `POST /api/camera/snapshot` (face-blurred, downscaled to 960×540, ≤300 KB, not stored), `ImageMarkup` with `single` box drawing, `shapeToBox` (fractions rounded to 3 places), `validate_box` and `decode_image` in `door_calibration.py`, and the `with_device` helper that resolves the account's first discovered device. The Config screen is a tab shell (`Config.tsx`) whose tabs are picked from the hash. All `/api/*` paths reach the API Lambda through one `/api/{proxy+}` route.

## Goals / Non-Goals

**Goals:**
- One saved fridge box per account and device, set from a live camera snapshot on the phone.
- Reuse the snapshot, drawing and validation code from door setup unchanged.

**Non-Goals:**
- Cropping anything with the box (follow-up change), deleting the area, several areas or cameras.

## Decisions

1. **Storage: one item per device.** `pk = ACCOUNT#<account_id>` (`account_pk`), `sk = FRIDGEAREA#<device_id>`, attributes `box` (a map `{x, y, width, height}`, as door references store it), `image` (Binary JPEG) and `updated_at` (ISO 8601 UTC with milliseconds). `PUT` overwrites the item, so there is no history and no limit to enforce. *Alternative:* store only the box. Rejected because the tab must show what the box was drawn on, and a later snapshot may differ if the camera moved, which is exactly what the owner needs to notice.
2. **Box stored as fractions of the image,** like door references. The crop in the follow-up works on any still size (Ring stills are 1920×1080; snapshots 960×540).
3. **Validation reused:** `fridge_area.save` calls `door_calibration.decode_image` and `validate_box`, so the error texts and the 2% minimum match the door references. No new constants.
4. **`PUT`, not `POST`:** there is exactly one area per device and saving replaces it, so the route is idempotent.
5. **New module `fridge_area.py`** (`save`, `load`, a frozen `FridgeArea` dataclass) rather than more code in `door_calibration.py`, which is about door references and setup runs. The follow-up crop will import `load` from here.
6. **PWA: `FridgeArea.tsx`** follows `DoorDetection.tsx`: `useLoad(api.fridgeArea)`, an editor `Sheet` holding the snapshot, `ImageMarkup` with `single` and the box tool, "Save" and "Cancel", and the `NO_FOOTAGE` message with "Try again". The saved area is shown with `ImageMarkup readOnly`.
7. **Three tabs at phone width:** the tab grid becomes `grid-cols-3`, and labels may wrap to two lines (`whitespace-normal leading-tight`, with the tab height growing to fit) instead of being shortened, so the existing tab names and their tests stay unchanged.

## Risks / Trade-offs

- **Archive order:** the `inventory-app` delta restates "Config screen" as `door-zone-setup` leaves it, plus the third tab. If `door-zone-setup` were archived after this change, it would overwrite the three-tab text. Archive `door-zone-setup` first.
- **Camera moves:** a saved box goes stale silently if the camera is bumped. The tab shows the snapshot the box was drawn on, so the owner can compare. Detecting movement is out of scope.
- **Item size:** a 300 KB image plus a few attributes stays under DynamoDB's 400 KB item limit, as with door references.

## Test strategy

- **Unit (pytest, moto DynamoDB):** `test_fridge_area.py` covers save/load, replace on save, invalid image or box leaves the stored area unchanged, and keying per device ("Fridge area kept per device").
- **API (pytest, moto, the existing `api_helpers` request builders):** `test_api_fridge_area.py` covers "No fridge area yet", "Viewer reads the fridge area", "Fridge area needs a camera", "Fridge area needs a token", "Fridge area saved" (clock frozen at 2026-10-16T01:00:00Z), "Saving again replaces the area", "Invalid fridge area rejected" and "Viewer cannot save the fridge area". No Ring or Rekognition call is made by these routes, so nothing else is stubbed.
- **Fixtures:** a small JPEG built with Pillow in the test (as in `test_api_door_calibration.py`), and a PNG for the rejection case. No new files under `tests/fixtures/`.
- **PWA (Vitest + Testing Library):** `client.test.ts` for the two methods' paths and bodies, `Config.test.tsx` for the tab scenarios, and `FridgeArea.test.tsx` for every "Fridge area tab" scenario, with the API mocked and the 400×225 rect mock used by the door-detection tests for drags.
- **Infra:** none changes, so no new CDK assertions.
