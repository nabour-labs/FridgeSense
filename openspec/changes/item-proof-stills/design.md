# Design

## Context

- `analysis.build_request` labels the stills "Image n of N" (at most 4), after any reference images, which are labelled "Reference n".
- `_CHANGE_SCHEMA` and the Pydantic `Change` model define each change.
- `inventory.save` builds each saved change record (`item`, `name`, `category`, `direction`, `quantity`, `confidence`, `applied`).
- The stored `still_keys` are the same stills, in the same order, as the ones sent to Nova, so image number n is `still_keys[n-1]`.
- `get_events` returns `changes` as saved, and presigns `still_keys` for events up to 7 days old.
- On Activity, `EventCard` shows the clip or the stills, and `StillViewer` steps through a `stills: string[]` list.

## Decisions

1. **Ask in the same call.** Add `images` to the per-change schema. Add one instruction line: "For each change, set images to the 1 or 2 image numbers where that item is most clearly visible." The field isn't required, so an older or terse answer still validates. There's no extra call and no extra cost line.
2. **Normalize in `Change`.** A `field_validator("images", mode="before")` keeps ints and integral floats, and rejects bools and strings. The range check against N needs the number of stills, so it happens in `NovaAnalyzer.analyze` after parsing, using `len(stills[:MAX_IMAGES])`. Converting to 0-based `proof` happens in `inventory.save`.
3. **Store indexes, not keys.** `proof` is a short list of numbers on the change record, and the API maps them to presigned `still_keys` links. Old records simply have no `proof`.
4. **UI:**
   - A `ProofStrip` component inside `EventCard`. The media area becomes `grid gap-3 sm:grid-cols-[2fr_1fr]`, and is a single column when there's no proof.
   - Each thumbnail button has the label "Proof for <label>, i of n".
   - Tapping one opens `StillViewer` with that change's proof list and a `titleFor` override, so the viewer's buttons use the proof labels.
   - The `StillLinks` cache key in `Activity.tsx` gets the proof link count too, so links refresh together.

## Risks / Trade-offs

- [Nova picks the wrong image] → only a hint. The clip and the other stills are still there, and wrong numbers are filtered out rather than trusted.
- [Stills are cropped to the visible strip, so the item may be half outside the frame] → accepted for the MVP. Cropping to the item is out of scope.
- [Answers cached under `novaCacheAnalysis`] → the cache covers only the input prefix, so the output changes are unaffected.

## Test strategy

- **Unit (pytest):** in `test_analysis.py`, test "Schema and prompt ask for images", "Out-of-range, duplicate and extra numbers", "Images missing or malformed" and "Non-integer numbers", using stubbed Converse responses (canned `toolUse` dicts). No Bedrock calls.
- **Integration (pytest + moto DynamoDB/S3):**
  - "Proof kept" through `inventory.save`.
  - In `test_api_events.py`: "Proof links listed", "Viewer gets proof", "Change without proof", "Index past the stored stills" and "Old event", with moto presigning.
- **PWA (Vitest):** in `Activity.test.tsx`, one test each for "Proof beside the clip", "Several changes", "Tap a proof still", "No proof", "Proof with stills" and "Layout by width" (class assertion). Update `fakeApi`/mock-api events to carry `proof`.
- No live AWS or Bedrock.
