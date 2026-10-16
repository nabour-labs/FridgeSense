# Proposal

## Why

The camera sees more than the fridge: the counter, the floor, people walking past. A later change will crop each still to the fridge before analysis, so Nova reads fewer pixels (lower cost) and is not distracted by things outside the fridge. For that, the app first needs to know where the fridge is in the camera's view, and the owner is the one who can say so, from the camera itself.

## What Changes

- **Config gets a third tab, "Fridge area"** at `#config/fridge`, next to "Reference images" and "Open/close detection". It shows the saved fridge area (the snapshot it was drawn on, with the box), or "No fridge area yet." when none is saved.
- The owner taps **"Set area"** ("Change area" once one exists). This takes a face-blurred camera snapshot. The owner drags one box around the fridge (a new drag replaces it) and taps **"Save"**. Viewers see the saved area read-only.
- **New API routes:** `GET /api/fridge-area` (owner and viewer) and `PUT /api/fridge-area` (owner) with `{"image", "box"}`. The area is stored per Ring account and device in DynamoDB. Saving again replaces it.
- Nothing uses the box yet: stills, door detection and Nova analysis are unchanged.

## Capabilities

### New Capabilities

- `fridge-area`: the owner's box around the fridge in the camera's view, stored per account and device and served over the HTTP API, for cropping stills later.

### Modified Capabilities

- `inventory-app`: "Config screen" goes from two tabs to three. A new requirement covers the "Fridge area" tab.

## Impact

- **Backend:** new `backend/src/fridgesense/fridge_area.py` (validate, save, load), reusing the box and JPEG validation from `door_calibration.py`. Two routes in `handlers/api.py`.
- **PWA:** `screens/Config.tsx` gains the third tab. New `screens/FridgeArea.tsx`, reusing `cameraSnapshot`, `ImageMarkup` (single box) and the snapshot error handling. `fridgeArea` and `saveFridgeArea` in `api/client.ts`, types in `api/types.ts`.
- **Infra:** none. The routes go through the existing `/api/{proxy+}` route to the API Lambda, which already has DynamoDB and Rekognition access.
- **Cost:** one face-detection call per snapshot (about $0.001). Nothing per door opening.
- **Order:** this change modifies the "Config screen" requirement as `door-zone-setup` leaves it, so `door-zone-setup` must be archived first.

**Hackathon tracks:** Ring (set up from the camera's own view) and AWS Builder.

**Out of scope:**
- Cropping stills or clips with the box, and any change to door detection or Nova analysis. That is the follow-up change.
- More than one area, polygons, or rotated boxes.
- Deleting the area (saving a new one replaces it).
- Choosing between several cameras: the account's first discovered device is used, as in door setup.
