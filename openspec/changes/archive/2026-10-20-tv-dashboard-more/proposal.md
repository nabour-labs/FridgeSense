# Proposal

## Why

The Fire TV kitchen dashboard (`firetv-kitchen-dashboard`) runs on the Vega Virtual Device with live data, but it leaves room on screen and has two visible flaws. The condiment icon is an empty box, because the TV's font has no 🫙. The remote's cursor, a teal circle, sits on top of the Opens panel. The phone app already has richer views that fit a TV glance well: the opens heatmap, open times and camera health. Adding them makes the Fire TV demo stronger at almost no backend cost.

## What Changes

- **Icons the TV can draw.** On the TV, an item whose icon is a newer emoji the Fire TV font lacks gets an older one: 🫙 (condiments, sauces, jam) becomes 🧂 and 🫑 (pepper) becomes 🌶️. The phone app is unchanged.
- **No cursor over the dashboard.** The TV dashboard hides the mouse pointer, so the remote's cursor no longer covers the panels.
- **Out of stock.** The In the fridge panel ends with "Out: milk, eggs" (at most 6 names, then "+N more") when items are at quantity 0.
- **Richer Recent changes.** Each row shows how long ago, the clock time and how long the door stayed open ("1 h ago · 8:42 pm · 12 s"), then the changes. Back-to-back openings with no changes collapse into one row: "3 openings · No changes".
- **Opens panel: open time and heatmap.** Under today's count: "Avg 12 s · Longest 40 s" for today. The 7-day bars get shorter, and a heatmap of opens by weekday and hour over the last 4 weeks goes below them, shaded as on the Stats screen.
- **Camera status line.** A line under the title shows the camera's name, Online / Offline (or "Status unknown" when Ring can't be reached), "Paused" when monitoring is paused, the 30-day uptime and whether motion detection is on. It comes from `GET /api/camera`, which every role, viewers included, can read. It refreshes every 5 minutes, because each read calls Ring. It shows no camera image.
- **Updated time.** The header shows "Updated 8:45 pm": when data last loaded.
- The dashboard now loads 28 days of openings instead of 7 (for the heatmap), and calls three endpoints instead of two: inventory, events and camera.

Out of scope:
- Camera pictures of any kind, including the camera's product image (`image_url`), live view, stills and clips.
- Anything to select or control on the TV, including pausing monitoring.
- Changing the phone app's icons, the Fire TV app shell, the backend or infra.
- Ask or voice questions on the TV.

Hackathon tracks: **Fire TV** (a better kitchen dashboard in the demo video).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `tv-dashboard`: the In the fridge, Recent changes and Opens panels gain the content above; new requirements for the camera status line, the updated time, TV-safe icons and the hidden cursor; "only two endpoints" becomes three. `tv-dashboard` is added by `firetv-kitchen-dashboard`, which must be archived before this change is.

## Impact

- PWA: `pwa/src/tv/tv.ts` (new pure helpers for timeline rows, out-of-stock names, open times, the camera line and TV icons), `pwa/src/tv/TvDashboard.tsx` (the new UI and a third `useLoad` for the camera), and their tests. The heatmap reuses `byWeekdayHour` and `heatLevel` from `stats.ts`.
- API: no changes; `GET /api/camera` already exists and lets viewers read it.
- Ring: one extra `GET /v1/devices/{id}` every 5 minutes while the TV dashboard is open.
- Fire TV app, backend, infra: none.
