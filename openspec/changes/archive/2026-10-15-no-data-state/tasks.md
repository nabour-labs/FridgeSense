# Tasks

## 1. Shared loading state

- [x] 1.1 Write failing tests in `pwa/src/useLoad.test.tsx` (stub fetch, fake timers) for "Still loading", "First load fails", "Data arrives later" and "Later poll fails" at hook level, plus `report` being called on each error; run `npm test -- useLoad` and verify they fail because the hook doesn't exist
- [x] 1.2 Implement `useLoad` in `pwa/src/useLoad.ts` on top of `usePolling`, returning `{ data, setData, failed }`; verify 1.1 passes
- [x] 1.3 Add `pwa/src/components/NoData.tsx` (a "No Data" message in the existing empty-state card style); it is covered by the screen tests below

## 2. Missing camera is quiet

- [x] 2.1 Write failing tests in `App.test.tsx` for "Missing camera is quiet" (three polls answering `ApiError(409)` show no "Something went wrong") and "Other errors still notify" (`ApiError(500)` shows it); run `npm test -- App` and verify the first fails
- [x] 2.2 Return early from `report` in `App.tsx` for `ApiError` with status 409; verify 2.1 passes

## 3. Screens

- [x] 3.1 Write failing tests in `screens/Fridge.test.tsx` for "No camera linked", "Data arrives later" (409 then eggs ×6 after 10 s), "Still loading" and "First load fails" (500 and `Offline`); verify they fail with the skeleton still present
- [x] 3.2 Move Fridge to `useLoad`, rendering `<NoData />` when it failed with nothing loaded; verify 3.1 and the existing "Empty fridge", "Fix a quantity" and "Live refresh" tests pass
- [x] 3.3 Write failing tests in `screens/Activity.test.tsx` for "No camera linked" and "Later poll fails" (events stay listed after a 500); then move Activity to `useLoad` and verify they pass with the existing tests
- [x] 3.4 Write failing tests in `screens/Review.test.tsx` for "No camera linked"; then move Review to `useLoad` (keeping the optimistic removal via `setData`) and verify they pass with "Confirm", "Reject" and "Nothing to review"
- [x] 3.5 Write failing tests in `screens/Stats.test.tsx` for "No camera linked"; then move Stats to `useLoad` and verify they pass with "No openings yet" and "Stats from events"
- [x] 3.6 Add an "Empty lists keep their messages" test per screen (200 with empty lists → existing message, no "No Data") and verify it passes
- [x] 3.7 Check all four screens with no camera linked in the dev preview at phone width, light and dark, and fix any layout issues found

## 4. Wrap-up

- [x] 4.1 Run `cd pwa && npm test && npm run build` green and report the commands and results
