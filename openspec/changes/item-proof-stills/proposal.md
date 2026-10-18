# Proposal

## Why

Activity says "+ soda" but doesn't show why. When a clip is shown, the stills are hidden, and nothing points at the moment the soda went in. Showing one or two stills per change, picked by the same Nova call that found the change, lets people check the answer at a glance and builds trust in the inventory.

Tracks: AWS Builder (Bedrock Nova), Open Source.

## What Changes

- The `record_fridge_changes` tool gets an optional `images` field per change: the 1 or 2 image numbers (from "Image n of N") where that item is most clearly visible. The prompt asks for it. This adds no Bedrock calls and only a few output tokens.
- The answer is still validated: numbers outside 1..N, duplicates, and anything past the first 2 are dropped. A missing or bad `images` gives `[]` and never fails the analysis.
- Each change saved on the door event keeps `proof`, the 0-based indexes into its `still_keys`.
- `GET /api/events` adds `proof` to each change: 15-minute links to those stills, or `[]` (old event, no proof, or proof saved before this change).
- Activity shows a "Proof" strip beside the clip on wide screens and below it on phones, with up to 2 thumbnails per change, each labelled with the change ("+ soda"). Tapping one opens it in the existing still viewer. Proof stills are the stored stills, which are already face-blurred.

## Out of scope

- Cropping or boxing the item inside the still.
- Proof on the pending-change confirm screen, in the MCP server or in assistant answers.
- Extra Nova calls to find better frames.
- Back-filling proof for old events.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `fridge-change-analysis`: adds "Proof images per change".
- `inventory-api`: adds "Proof still links per change".
- `inventory-app`: adds "Proof stills on Activity".

## Impact

- Backend: `analysis.py` (tool schema, prompt line, `Change.images`), `inventory.py` (the saved change record keeps `proof`), and `handlers/api.py` (`get_events`).
- PWA: `api/types.ts` (`Change.proof`), `screens/Activity.tsx`, and the mock API.
- README: the Activity section.
- No infrastructure change, and no change to the number or cost of Nova calls beyond about 10 extra output tokens per change.
- It adds requirements only, so it doesn't conflict with `blur-faces-in-clips`, which modifies "Door event listing".
