## Why

The Stats screen's 24-cell "Opens by hour" strip shows when in the day the fridge is opened, but not on which days. A weekday × hour heatmap, styled like GitHub's contribution graph, shows the weekly habit at a glance (for example "Sunday evenings").

Tracks: **Ring** (insight built on door events).

## What Changes

- Replace the "Opens by hour" strip with an "Opens by day and hour" heatmap: 7 rows (Sun–Sat) × 24 columns (00–23), each cell shaded in one of 5 levels, with weekday labels on Mon/Wed/Fri, hour labels every 6 hours and a "Less … More" legend.
- The heatmap covers the last 28 days so each weekday row has up to 4 days of data. Stats now requests `GET /api/events?days=28`.
- The tiles and the per-day bar chart still use only the last 7 days.

## Out of scope

- Picking the time range in the UI.
- Any API or backend change (`days` already allows up to 30).

## Impact

- `pwa/src/stats.ts`, `pwa/src/screens/Stats.tsx` and their tests.
- No new AWS resources, no cost.
