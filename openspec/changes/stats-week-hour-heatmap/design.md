## Context

Stats computes everything on the device, in the device's time zone, from `GET /api/events`. The hour strip is a hand-built CSS grid, not Recharts.

## Decisions

- **Hand-built CSS grid, no new library.** `grid-template-columns: auto repeat(24, 1fr)` with square cells fits 360 px phones (cells are about 11 px).
- **Rows Sun–Sat, labels on Mon/Wed/Fri**, matching GitHub's layout.
- **Five discrete levels** instead of continuous opacity: level 0 for no opens, otherwise `ceil(4 × opens / max)`, so the busiest cell is always level 4. Light mode goes `brand-200 → brand-800`; dark mode goes `brand-900 → brand-300` so busier cells are brighter, as on GitHub.
- **28 days of events.** One fetch of 28 days; `lastDays(events, now, tz, 7)` filters the list for the tiles and the bar chart.
- **Accessibility.** The grid is `role="table"` with `role="row"`/`role="cell"`; each cell has an `aria-label` like "Mon 19:00, 2 opens" and a matching `title` for hover.

## Test strategy

- Unit (Vitest, `src/stats.test.ts`): `byWeekdayHour`, `heatLevel`, `lastDays`, including the time zone case.
- Component (Vitest + Testing Library, `src/screens/Stats.test.tsx`): the figure has 168 labelled cells, a legend, the API is asked for 28 days, and an event 10 days old shows in the heatmap but not in "Last 7 days".
- Events are built in the test; the API is the existing `fakeApi` stub.
