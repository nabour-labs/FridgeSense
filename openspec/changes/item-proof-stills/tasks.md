# Tasks

## 0. Branch

- [x] 0.1 Branch `feat/item-proof-stills` off `local`.

## 1. Nova picks proof images (backend)

- [x] 1.1 Write failing tests in `backend/tests/test_analysis.py` for "Schema and prompt ask for images", "Out-of-range, duplicate and extra numbers", "Images missing or malformed" and "Non-integer numbers". Keep every "Answer validated before use" test passing. Run them red.
- [x] 1.2 Add `images` to `_CHANGE_SCHEMA`, add the instruction line, add `Change.images` with its validator, and add the range filter in `NovaAnalyzer.analyze`. Verify that 1.1 passes.

## 2. Proof saved with each change (backend)

- [x] 2.1 Write a failing moto test for "Proof kept" (the saved change has `proof = [2, 3]`), and check that the existing save tests still pass. Run it red.
- [x] 2.2 Save `proof` in `inventory.save`'s change record. Verify that 2.1 passes.

## 3. Proof links in the listing (backend)

- [x] 3.1 Write failing tests in `test_api_events.py` for "Proof links listed", "Viewer gets proof", "Change without proof", "Index past the stored stills" and "Old event". Run them red.
- [x] 3.2 Map each change's `proof` to presigned still links in `get_events`. Verify that 3.1 and the whole "Door event listing" suite pass.

## 4. Proof strip on Activity (PWA)

- [x] 4.1 Add `proof: string[]` to `Change` in `api/types.ts`, and give the fakes and `scripts/mock-api.ts` sample proof.
- [x] 4.2 Write failing tests in `Activity.test.tsx` for "Proof beside the clip", "Several changes", "No proof", "Proof with stills" and "Layout by width". Run them red.
- [x] 4.3 Implement `ProofStrip` and the two-column media grid. Verify that 4.2 passes.
- [x] 4.4 Write a failing test for "Tap a proof still". Then open `StillViewer` with the proof list and labels, and verify it passes.

## 5. Docs and checks

- [x] 5.1 Update the README Activity section.
- [x] 5.2 Run `cd backend && uv run pytest && uv run ruff check` and `cd pwa && npm test && npm run typecheck`, all green, and report the result.
