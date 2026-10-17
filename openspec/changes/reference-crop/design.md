# Design

## Context

`AddReference` keeps the picked image as a `Blob` (`source`) plus a preview URL, and the drawn `shapes`. On Save, `resize(source, shapes)` (`image.toJpeg`) scales to 768 px, burns the shapes in red and returns base64.

## Decisions

- **Crop in the browser, from the source blob.** A `Crop = (file: Blob, box: Shape) => Promise<Blob>` in `image.ts` draws the box region of the full-resolution bitmap onto a canvas and returns a JPEG (quality 0.92). The usual resize then runs on Save, so a small crop keeps its detail and a crop larger than 768 px is still capped.
- **Pixel rect is a pure helper.** `cropRect(width, height, shape)` returns `{x, y, width, height}` in whole pixels, at least 1×1 and inside the image, so it is unit-tested without a canvas.
- **Crop to the last box.** With the Line tool gone every shape is a box; the last one is what the owner just drew.
- **Crop undo stack.** Before each crop, `{source, preview, shapes}` is saved. "Undo" pops a shape first; with none left, it restores the saved image. Undo steps back one crop at a time.
- **Injected like `resize`.** `Config` and `ReferenceImages` take `crop = cropJpeg`, so tests pass a `vi.fn` (jsdom has no `createImageBitmap`).

## Risks / Trade-offs

- A box drawn on a cropped image is burned into the smaller image, so its stroke looks relatively thicker. Acceptable.
- Re-encoding twice (crop at 0.92, then 0.8) loses a little quality; not visible at 768 px.

## Test strategy

- **Unit (vitest):** `image.test.ts` for `cropRect` (fractions to pixels, rounding, clamped inside, at least 1 px).
- **Component (vitest + Testing Library):** `Config.test.tsx` with a stubbed `crop`: no Box/Line buttons; "Crop" disabled without a box; Crop calls `crop(source, lastBox)`, shows the cropped image, clears boxes, and Save uploads the cropped blob; Undo after a crop restores the previous image and its box.
- Nothing calls live AWS or Bedrock.
