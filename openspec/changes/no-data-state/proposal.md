# Proposal

## Why

When there is nothing in the database for the app to show, the Fridge, Activity, Review and Stats screens get stuck on their grey loading skeleton forever. The typical case is a camera that isn't linked yet, so every `/api` call answers 409 `{"error": "no camera linked"}`. The same happens when the very first request fails. Each screen keeps its data at `null` while it waits, and the shell pops a "Something went wrong" toast on every poll. For a judge opening the demo link, this looks like a broken app rather than an empty one.

Tracks: **Ring** and **AWS Builder**, through the polish of the demo app that front-ends both.

## What Changes

- **Show "No Data" when a load fails.** On each of the four screens, once the first load has failed, the skeleton is replaced by a plain "No Data" message.
  - This covers 409 "no camera linked", other API errors and being offline.
  - The skeleton still shows while the first request is in flight.
- **Keep polling.** As soon as a later poll returns data, the screen shows its normal content.
- **No toast for a missing camera.** A 409 "no camera linked" answer no longer pops "Something went wrong", because it is an expected state.
  - Other errors keep their current handling: the 401 sign-out, the offline banner, the 403 read-only notice and the generic toast.
- **Unchanged:** the existing empty-list messages, shown when the API answers successfully with empty lists:
  - "Your fridge looks empty", plus the hint about the next door opening
  - "No door openings in the last 7 days"
  - "Everything is confirmed"
  - zero tiles and empty bars on Stats

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `inventory-app`: adds a requirement that a screen with nothing loaded shows "No Data" instead of a skeleton, and that a missing camera raises no error toast.

## Out of scope

- **Changing the API.** 409 "no camera linked" stays as it is.
- **Changing the empty-list wording** on any screen.
- **A "link your camera" call to action or onboarding flow.**
- **Caching data across reloads** so there is something to show while offline.
- **The Config screen** (`config-and-daily-sign-in`) and the Ask screen (`voice-page`). Those changes can adopt the same "No Data" component when they are built.

## Impact

- **PWA only:**
  - `screens/Fridge.tsx`, `Activity.tsx`, `Review.tsx` and `Stats.tsx`
  - a small shared `components/NoData.tsx`
  - the `report` handler in `App.tsx`, which silently drops 409 "no camera linked"
  - tests next to each screen
- **No backend, infra or dependency changes.** It deploys with the PWA assets.
- **Overlap:** `App.tsx` is also edited by the `voice-page` and `config-and-daily-sign-in` changes. The edit here is a couple of lines in `report`.
