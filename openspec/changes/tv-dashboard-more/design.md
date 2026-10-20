# Design

## Context

The TV dashboard is `pwa/src/tv/TvDashboard.tsx`, a thin UI over pure helpers in `pwa/src/tv/tv.ts`. It has two `useLoad` calls (inventory every 10 s, `events(7)` every 30 s) and three panels. The Stats screen already has the counting this change needs: `perDay`, `lastDays`, `byWeekdayHour`, `heatLevel` and `durationStats` in `stats.ts`, and it loads `events(28)` for its heatmap. The Camera screen reads `GET /api/camera` (`CameraInfo`), which also calls Ring's device endpoint on every read. In the Fire TV app (`firetv/`), the Vega WebView exposes no prop to hide its remote cursor; the typed props have nothing about a cursor or pointer.

`tv-dashboard` exists only as a delta in the unarchived `firetv-kitchen-dashboard` change. That change has to be archived first so this one's MODIFIED requirements have a base.

## Goals / Non-Goals

**Goals:**
- Keep `tv.ts` the home of all TV logic, so each scenario is a plain unit test.
- Reuse the Stats screen's counting so the TV and phone never disagree.
- Keep the 1920×1080 layout to three columns and one header.

**Non-Goals:**
- A shared emoji-compatibility layer for the whole app; only the TV gets the fallbacks.
- Changes to the Fire TV app shell.

## Decisions

1. **One events load of 28 days.** Switch the dashboard to `api.events(28)` and take the last 7 days with `lastDays` for Recent changes, the bars and today's numbers; the heatmap uses all 28. *Alternative:* a second 28-day load on a slower timer. That means more requests and two sources of truth for the same openings.
2. **Camera on its own 5-minute `useLoad`.** Each `GET /api/camera` calls Ring, so 30 s polling from a TV that stays on all day is too much. 5 minutes keeps the status line fresh enough and adds 288 Ring calls a day at most. *Alternative:* derive status from events only. That misses offline status and uptime.
3. **Camera line in the header, not a fourth panel.** The camera has 4–5 short facts; a header line keeps the three panels at full width. The title row becomes: "FridgeSense" on the left and "Updated 8:45 pm" on the right, with the camera line below it.
4. **TV icon map, not a font.** `tvIcon(name, category)` wraps `itemIcon` and swaps 🫙→🧂 and 🫑→🌶️. These are the only two Emoji 13+ symbols in `itemIcon.ts`; the rest render on the Vega WebView (seen on the device). *Alternative:* bundle an emoji web font (Noto Color Emoji is ~10 MB) or use SVG icons. Both are heavy for two glyphs.
5. **Collapse in `recentRows`.** Collapse runs on the 7-day openings sorted newest first, before taking 5 rows, so the panel shows 5 rows of history. A collapsed row keeps its newest opening's id, time and duration, plus a `count`.
6. **Hide the cursor with CSS.** `cursor: none` on the dashboard root (Tailwind `cursor-none`). Pages commonly do this to hide a WebView's emulated pointer. *Fallback:* if the Vega cursor is native and ignores CSS, leave it, log the friction, and look for a Vega setting later. The dashboard has nothing to select, so the cursor is cosmetic.
7. **Heatmap as a CSS grid of `<span>`s** with an `aria-label` per cell ("Mon 8 am: 4 opens") and the Stats screen's level colours, adjusted for the dark background. No Recharts. *Alternative:* reuse the Stats `Heatmap` component. It's private to `Stats.tsx` and sized for a phone (10 px labels); a TV version is ~25 lines.
8. **Times with `Intl.DateTimeFormat`** (`hour: "numeric", minute: "2-digit"`, lowercased: "8:42 pm") in the device's time zone, in one `clockTime` helper used by the timeline and "Updated".

## Risks / Trade-offs

- [The Vega cursor ignores CSS] → Decision 6's fallback; the change still ships everything else.
- [28 days of events every 30 s is a bigger response] → At about 10 openings a day that's ~280 small rows: fine. If it grows, slow the refresh to 60 s as on the Stats screen.
- [Ring rate limits from the camera poll] → Every 5 minutes is far below anything Ring has rejected so far, and the endpoint already answers 200 with `ring: "unavailable"` when Ring fails.
- [The heatmap is cramped in a ~520 px column] → 24 cells at ~18 px with labels every 6 hours; checked at 1920×1080 in the browser preview and on the Vega Virtual Device.

## Migration Plan

Archive `firetv-kitchen-dashboard` first (its last task is effectively done: the dashboard ran on the Vega Virtual Device with live data). Then this change ships with the next PWA deploy; the Fire TV app needs no rebuild, since it loads the site. Rollback is redeploying the previous PWA.

## Test strategy

- **Unit (Vitest), `pwa/src/tv/tv.test.ts`:** `recentRows` (time, duration, collapse, analyzing, 7-day cut), `outOfStock`, `openTime`, `cameraLine`, `tvIcon`, `clockTime`, plus the heatmap cell labels and levels. Fixed `now` and an explicit time zone (`America/Vancouver`), as the existing tests do.
- **Component (Vitest + Testing Library), `pwa/src/tv/TvDashboard.test.tsx`:** the camera line and "Camera: No Data", "Updated" text, three endpoints only, `days=28`, no `img` for `image_url`, no controls, `cursor: none`, camera refresh at 5 minutes and not at 30 s (fake timers), TV icons in rows. The API is the existing mocked client from `test-utils.tsx` with canned `CameraInfo`, inventory and events.
- **Phone unchanged:** an `itemIcon.test.ts` case that "ketchup" stays 🫙.
- **Manual:** browser preview at 1920×1080 (`pwa-mock`), then the Vega Virtual Device against the deployed site after deploy. No live Ring or AWS calls in tests.
