# Tasks

## 1. Crop rectangle (PWA unit)

- [x] 1.1 Write failing tests in `image.test.ts` for `cropRect` (scenario "Crop to the box"). Verify they fail because `cropRect` is missing
- [x] 1.2 Implement `cropRect` and `cropJpeg` in `image.ts`. Verify the 1.1 tests pass

## 2. Reference sheet (PWA)

- [x] 2.1 Update `Config.test.tsx`: "Draw on the image" drags boxes only and checks there are no "Box"/"Line" buttons; add failing tests for "Crop to the box", "Crop needs a box" and "Undo a crop". Verify they fail
- [x] 2.2 Remove the tool buttons, add "Crop" and crop undo to `AddReference`, and pass `crop` through `Config`. Verify the 2.1 tests and every existing reference-image test pass

## 3. Wrap up

- [x] 3.1 Run `cd pwa && npm test && npm run typecheck` (and lint if configured) green and report the result
