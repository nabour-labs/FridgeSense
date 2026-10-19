# Proposal

## Why

A reference image can only be added or deleted. To fix a typo in its note, clarify it ("these are not beer, these are fridge magnets…") or swap in a better photo, the owner has to delete it and add it again, which loses its place in the list and means redrawing the image from scratch.

## What Changes

- **New route.** `PATCH /api/config/references/{id}` with `{"annotation"?: "<text>", "image"?: "<base64 JPEG>"}` changes the annotation, the image or both of an existing reference, with the same limits as adding. The reference keeps its id, `created_at` and place in the list. It returns the full config. An empty body is 400; an unknown id is 404; viewers get 403.
- **Edit button.** Each reference card gets an "Edit" (pencil) button next to "Delete" for the owner. It opens an "Edit reference" sheet with the current image and annotation filled in. The owner can change the note, draw or crop on the current image, or replace it with "Choose photo", "Camera snapshot" or "Recent clip", exactly as when adding. "Save" sends only what changed and is disabled until something has.

Out of scope: reordering references, keeping an edit history.

## Capabilities

### Modified Capabilities

- `analysis-config`: a route to edit a reference.
- `inventory-app`: an Edit button and sheet for a reference.

## Impact

- Backend: `analysis_config.update_reference`; `PATCH /api/config/references/{id}` in `handlers/api.py`. Same DynamoDB item, no migration. The API Gateway `/api/{proxy+}` route already takes any method.
- PWA: `api/client.ts` (`updateReference`), `AppContext.tsx`, `test-utils.tsx`, `screens/ReferenceImages.tsx` (the add sheet becomes a shared add/edit sheet).
- Cost: none beyond one DynamoDB read and write per edit.
