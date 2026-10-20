# Proposal

## Why

The TV dashboard now has the phone app's camera info, stats and timeline, but no pictures. On the phone, the photos are the convincing part: the Activity screen shows the still where Nova saw the milk go in. Without them, a viewer of the Fire TV demo has to take the text on trust. The openings the TV already loads carry these pictures as presigned links, for every role, so adding them needs no backend work.

## What Changes

- **Proof photos in Recent changes.** A row whose opening has changes shows small photos under its labels: the first proof still of each change that has one, at most 3 per row, in the order of the labels. Rows with "Checking…" or "No changes" show none.
- **Latest still in the header.** The header shows the newest still of the newest opening that has stills, with its caption "Latest still · 8:42 pm". It comes from the openings already loaded, so it updates with the 30 s events refresh. With no stills in the last 7 days, the header has no picture.
- **Broken links hide.** A photo that fails to load (an expired or missing link) is removed instead of showing a broken image; the next refresh brings fresh links.
- **BREAKING (spec only):** "Nothing private or interactive on the TV dashboard" no longer bans stills and proof photos. It still bans clips, live view, reference images, the camera's product image (`image_url`) and camera snapshots, and still allows only the inventory, events and camera endpoints.

Out of scope:
- Clips or video of any kind, live view, `POST /api/camera/snapshot` and `POST /api/camera/frame` (viewers can't call them, and each calls Ring).
- Opening a photo larger, or anything else to select on the TV.
- The camera's product image (`image_url`), reference images.
- Changes to the backend, infra, the phone app or the Fire TV app shell.

Hackathon tracks: **Fire TV** (the demo video shows the evidence on the kitchen TV); supports **Ring** (Ring stills, shown where the household looks).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `tv-dashboard`: Recent changes rows gain proof photos; a new requirement for the latest still in the header; "Nothing private or interactive on the TV dashboard" allows stills and proof photos. This builds on `tv-dashboard-more`, which must be archived first.

## Impact

- PWA: `pwa/src/tv/tv.ts` (proof links on `RecentRow`, a `latestStill` helper), `pwa/src/tv/TvDashboard.tsx` (thumbnails, header still, hide-on-error), and their tests.
- Network: at most 16 small JPEGs on screen (5 rows × 3, plus the header). Each refresh signs new links, so a photo already shown keeps its old link while it is on screen; only new photos download.
- API, backend, infra, Ring, Bedrock, Fire TV app: no changes.
- Privacy: stills are shown to whoever sees the TV. They are face-blurred when the owner's face-blur setting is on (the default), as on the phone's Activity screen.
