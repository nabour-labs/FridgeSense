# Proposal

## Why

Every reference image goes to Nova with each analysis prompt, and image tokens grow with the pixel count. A reference is usually one item in a busy fridge shot, so most of the 768 px image is background the model pays for and doesn't need. Letting the owner crop to the box they drew sends only the item, at higher detail and lower cost. The "Line" tool has no real use, so it goes.

Hackathon tracks: **AWS Builder** (lower Bedrock Nova token cost per analysis).

## What Changes

- "Add a reference" drops the "Box" and "Line" tool buttons. Dragging always draws a box.
- Once a box is drawn, a "Crop" button crops the image to the last box. The cropped image replaces the one shown, and its boxes are cleared.
- "Undo" removes the last box; with no boxes left after a crop, it restores the image from before the crop, with its boxes.
- The crop is taken from the full-resolution source, then the upload re-encodes it as today (JPEG, longer side at most 768 px).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-app`: "Manage reference images" loses the Line tool and gains "Crop".

## Out of scope

- Cropping existing references, or the Open/close detection and Fridge area snapshots.
- Removing line support from the shared `shapes.ts` / `ImageMarkup` code (kept for later use).
- Backend changes: the API still accepts any JPEG within its limits.
- Fire TV and MCP.

## Impact

- PWA: `screens/ReferenceImages.tsx`, `screens/Config.tsx` (passes the crop function), `image.ts` (crop helper).
- Cost: fewer Nova input tokens for every analysis that uses a cropped reference.
