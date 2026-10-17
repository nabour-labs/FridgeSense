# Design

## Context

`Stats.tsx` loads `api.events(28)` once a minute and derives everything in `useMemo` through pure helpers in `stats.ts` (`perDay`, `lastDays`, `averageDuration`, all time-zone aware via `dayKey`). `DoorEvent.duration_s` is a number on every event the API returns, so the data is already on the client.

## Goals / Non-Goals

**Goals:** a pure, unit-tested per-day summary; a small accessible card that fits at 375 px.

**Non-Goals:** new API fields, caching, persisting the selected day across visits.

## Decisions

1. **PWA-only.** `GET /api/events?days=28` already returns `duration_s`. Alternative (a backend aggregate endpoint) adds Lambda code and tests for data the client already holds.
2. **`durationStats(events, date, timeZone)` in `stats.ts`** returns `{ average, longest, shortest } | null` for the events whose local `dayKey` equals `date` (YYYY-MM-DD). Reuses `dayKey` so the day boundary matches `perDay`. Average uses `Math.round` like `averageDuration`.
3. **`duration(seconds)` in `format.ts`**: `"45 s"` below 60, else `` `${m} m ${ss} s` `` with `ss` padded. Kept separate from the existing tile, which still shows `"30 s"` (its values are typically short; changing it is out of scope).
4. **Day picker = 7 toggle buttons** (`aria-pressed`) built from `perDay(...)` (dates and short weekday labels already computed; today's label replaced with "Today"). Chosen over making chart bars clickable (Recharts bars aren't keyboard reachable and are awkward to test) and over a `<select>`/date input (more taps, and older days are out of the 7-day window anyway). Selected date lives in `useState<string | null>`, `null` meaning today, so the default follows midnight rollovers on the 60 s refresh.
5. **Layout:** a `Chart`-style `figure` named "Open time". Buttons in a 7-column grid (each ≈ 40 px wide at 375 px). Values in a 3-column grid of `Tile`s labelled Average / Longest / Shortest, reusing the existing `Tile` (`role="group"` + `aria-label`) so tests query by name.
6. **All statuses count.** A door opening is real whether or not Nova analysis succeeded.

## Risks / Trade-offs

- [Tile label collision: "Average" vs existing "Average open time" group] → distinct accessible names; tests query within the "Open time" figure.
- [Tiles too narrow for "10 m 00 s" at 375 px] → slightly smaller value text in this card; verified in the 375 px preview.

## Test strategy

- **Unit (Vitest, `stats.test.ts`, `format.test.ts`):** `durationStats` for Average rounded, Single opening, Day without openings (null), Open time in local days (America/Vancouver); `duration` for Minutes and seconds.
- **Component (Vitest + Testing Library, `Stats.test.tsx`):** Today's open times, Pick another day (user click), Seven day buttons, Long opening on the card, Day without openings — via `App` with `fakeApi` events, as the existing Stats tests do. No network; no fixtures beyond in-test events.
- **Manual:** `pwa-mock` preview at 375 px and desktop.
