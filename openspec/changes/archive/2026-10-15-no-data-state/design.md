# Design

## Context

Each of the four screens follows the same pattern:

- `useState<T | null>(null)`, plus a `load` callback that calls the API, then `setX(data); online()` on success and `report(err)` on failure.
- `usePolling(load, interval)`.
- `if (!x) return <skeleton>`.

Failures never change the state, so a screen with no data stays on the skeleton.

The `ApiClient` throws `ApiError(status)` for non-2xx responses other than 401 and 403, and drops the body. The 409 "no camera linked" answer is the only 409 the app API returns (`handlers/api.py`). `App.report` sends `ApiError` to the generic "Something went wrong" notice.

## Goals / Non-Goals

**Goals:**

- One shared way to track "loading / loaded / failed with nothing" across the four screens.
- Tests of the observable states.

**Non-Goals:**

- Restyling the skeletons or the empty-list messages.
- Error details on the screen. "No Data" is deliberately plain.

## Decisions

### 1. A small `useLoad` hook

`useLoad<T>(fetch: () => Promise<T>, intervalMs)` wraps `usePolling` and returns `{ data, setData, failed }`.

- **On success:** it sets `data`, clears `failed` and calls `online()`.
- **On error:** it calls `report(err)`, then sets `failed = true`.
- **Rendering:**
  - Skeleton when `data === null && !failed`
  - `<NoData />` when `data === null && failed`
  - Otherwise, the normal content
- `failed` never hides data that has already loaded, which covers "Later poll fails".
- `setData` stays exposed, because Review removes items optimistically and Fridge replaces the inventory after an edit.
- *Alternative:* add a `failed` state by hand in each screen. That repeats the same 3-state logic four times, and the review risk is in the edge cases.

### 2. Treat 409 as "no camera" in `report`, by status

`App.report` returns early for `ApiError` with `status === 409`.

- *Alternative:* parse the body for `"no camera linked"`. That needs `ApiError` to carry the body. The `config-and-daily-sign-in` change adds the message anyway, so the check can be tightened then.
- Today the API has no other 409, so checking the status alone is accurate.

### 3. A shared `components/NoData.tsx`

It renders a centered, muted "No Data" paragraph in the same card style as the existing empty states, without `aria-hidden`, so screen readers announce it.

## Risks / Trade-offs

- **[A future 409 on a read route would be silenced]** → Today 409 is only "no camera linked". When `ApiError` carries the server's message (planned in `config-and-daily-sign-in`), match on it.
- **[A transient error at startup shows "No Data" for one poll interval]** → This is acceptable, and the next poll recovers.
- **[Merge overlap in `App.tsx`]** → The change is a two-line guard in `report`, so it rebases easily.

## Migration Plan

Nothing to migrate. It ships with the next PWA deploy (`cdk deploy`, which deploys the site assets). To roll back, redeploy the previous build.

## Test Strategy

- **Unit (Vitest):**
  - `src/useLoad.test.tsx` uses a stub fetch and fake timers. It covers:
    - loading → data
    - loading → failed → data on the next poll
    - data → failed poll keeps the data
    - `report` is called on errors
- **Component (Vitest + Testing Library):**
  - Extend `Fridge.test.tsx`, `Activity.test.tsx`, `Review.test.tsx` and `Stats.test.tsx`, using the existing injected stub API from `test-utils.tsx`.
  - Each screen gets "No camera linked" (a stub rejects with `new ApiError(409)` → "No Data" is shown and no skeleton element remains) and "Empty lists keep their messages".
  - Fridge also covers "Data arrives later". Activity also covers "Later poll fails". One screen covers "Still loading" and "First load fails", for both an `ApiError(500)` and an `Offline` rejection.
- **Shell (Vitest):** `App.test.tsx` covers "Missing camera is quiet" (three 409s, no "Something went wrong") and "Other errors still notify" (a 500 shows the notice).
- **Fixtures:** none new. No network; the API is stubbed.
