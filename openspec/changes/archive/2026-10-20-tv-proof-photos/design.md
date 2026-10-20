# Design

## Context

After `tv-dashboard-more`, the TV dashboard (`pwa/src/tv/TvDashboard.tsx`) loads `api.events(28)` every 30 s and renders Recent changes from `recentRows` in `pwa/src/tv/tv.ts`. Each `DoorEvent` already carries `stills` (presigned S3 links, 15 min TTL, only for openings in the last 7 days) and each `Change` a `proof` array (up to 2 links into those stills). The API returns both to every role, viewers included. Stored stills are face-blurred when the face-blur setting is on. `POST /api/camera/snapshot` is a write route (viewers get 403) and calls Ring, so it is not an option for a TV that is often signed in as a viewer.

The 1920×1080 layout has a header (title, "Updated", camera line) and three panels; Recent changes is about 520 px wide and 800 px tall, holding 5 rows today.

## Goals / Non-Goals

**Goals:**
- No new endpoint, no new request: every picture comes from the openings already loaded.
- Keep picture logic in `tv.ts` as pure functions, unit-tested like the rest.
- Keep 5 rows in Recent changes at 1920×1080.

**Non-Goals:**
- A live or on-demand camera picture.
- Reusing the Activity screen's `ProofStrip` or `Stills` components (they are buttons that open a sheet, sized for a phone).

## Decisions

1. **"Latest camera still" = the newest opening's last still.** `latestStill(events, timeZone)` walks openings newest first and returns `{ src, caption }` from the first one with stills, using the last still (closest to the door closing), or null. *Alternative:* `POST /api/camera/snapshot`. Viewers can't call it, it calls Ring, and it runs face blur on every request.
2. **Proofs on `RecentRow`.** `recentRows` gains `proofs: string[]` per row: the first `proof` link of each non-rejected change, in label order, capped at 3 (`MAX_PROOFS`). Rows in the "checking" and "none" states, including collapsed rows, get `[]`. This keeps the order tied to the labels the same function builds.
3. **Thumbnails at 56 px tall, 4:3, `object-cover`, in one row under the labels; only whole rows show.** Three fit in the ~430 px column. A row with photos is ~132 px, plus 20 px between rows, so 5 rows that all have photos need ~740 px, and the panel has ~709 px (measured at 1920×1080). The list is a wrapping flex column: a row that doesn't fit whole moves to a second column outside the panel, so the panel shows 4 whole rows in that worst case and 5 otherwise, never half a photo. *Alternatives:* smaller thumbnails (unreadable across a room); a 4-row cap whenever any row has photos (wastes space in the common case of one or two photo rows).
4. **Header still on the right.** The title row becomes title on the left, and on the right a 16:9 image ~120 px tall with "Latest still · 8:42 pm" and "Updated 8:45 pm" stacked beside it. The camera line stays under the title.
5. **Stable links: photos keyed by the link without its query string.** Each events refresh re-signs every link, which would make the browser re-download every photo every 30 s and flash. Each photo element gets `key={stillBase(src)}`, and a `useStillSrc` hook keeps the first link it was given. A new link for the same picture reuses the element and its old link; a different picture is a new element. A kept link expires after 15 min, but the browser already holds the decoded image, so the `img` keeps painting. If the element is re-created after its link expired, `onError` fires, and decision 6 handles it. *Alternatives:* a shared `Map<base, src>` hook (more state to prune, same effect); a longer TTL on the backend (a backend change, and it weakens the links for every client).
6. **Hide on error, come back on refresh.** `useStillSrc` also holds a `failed` flag: after `onError` it returns null and the photo (and, in the header, its caption) is not rendered. When a refresh brings a different link for that picture, it takes the new link and clears the flag.
7. **`loading="lazy"` off, `decoding="async"` on.** Everything is on screen at once; lazy loading only delays it in the Vega WebView.

## Risks / Trade-offs

- [People in stills on a shared TV] → Face blur is on by default and applies to stored stills; the proposal states this. Owners who turn it off see the same on the phone.
- [The Vega WebView may be slow decoding 16 JPEGs] → They are small Ring stills; checked on the Vega Virtual Device in task 4.2. If slow, cap proofs at 2 per row.
- [Expired kept links after a re-render] → Decision 6: the photo hides and returns with the next refresh (≤ 30 s).
- [Stills only exist for the last 7 days] → Recent changes only shows the last 7 days, so rows never miss photos for that reason; the header shows nothing after a quiet week, as specified.

## Migration Plan

Archive `tv-dashboard-more` first (its task 3.1 is the on-device check after deploy), so the MODIFIED requirement has a base. Ships with the next PWA deploy; the Fire TV app needs no rebuild. Rollback is redeploying the previous PWA.

## Test strategy

- **Unit (Vitest), `pwa/src/tv/tv.test.ts`:** `recentRows` proofs (order, first link only, cap of 3, rejected and missing proofs, none for checking/none/collapsed rows); `latestStill` (newest opening's last still, skips openings without stills, null when none, caption clock time with `America/Vancouver`); `stillBase` (strips the query string).
- **Component (Vitest + Testing Library), `pwa/src/tv/TvDashboard.test.tsx`:** thumbnails rendered with the right `src` and empty `alt`; header image and caption; no header image when no stills and when events fail; `fireEvent.error` removes a photo (and the header caption); re-signed link kept across a refresh with fake timers (30 s); new latest still replaces the old; every `img` `src` is a still or proof link; no `video`; no `image_url`; no snapshot request; no controls. Canned `DoorEvent`s with fake `https://s3/...` links from the existing mocked client in `test-utils.tsx`. No live S3, Ring or Bedrock.
- **Mock server:** the `pwa-mock` events already have stills and proofs; check that they render at 1920×1080.
- **Manual:** browser preview at 1920×1080, then the Vega Virtual Device after deploy.
