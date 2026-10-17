# Proposal

## Why

The Stats screen shows one number for how long the door stays open: the average over the last 7 days. It can't answer "how long was the fridge open today?" or show the one long opening that warmed it up. Every door event already carries `duration_s`, so the PWA can show a day's average, longest and shortest opening without any backend change.

Tracks: Ring (more value from the camera's door events) and AWS Builder (PWA on the existing API).

## What Changes

- New "Open time" card on the Stats screen, below "Opens per day". It shows the **Average**, **Longest** and **Shortest** time the door was open on the selected day.
- A row of 7 day buttons (the same last 7 days as the bar chart, oldest first, the last one labelled "Today") picks the day. Today is selected when the screen opens.
- Durations under a minute read "45 s"; a minute or more reads "1 m 05 s" (seconds padded to 2 digits). The average is rounded to the nearest second.
- A day with no openings shows "–" for all three values and "No openings".
- Days are local days in the device's time zone, like the rest of the Stats screen.

Out of scope: backend or API changes, a date picker for days older than 7 days, durations in the heatmap or bar chart, per-hour breakdowns, changing the existing 7-day "Average open time" tile, excluding events by status.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `inventory-app`: adds a "Daily open-time stats" requirement to the Stats screen.

## Impact

- `pwa/src/stats.ts`: a per-day duration summary helper; `pwa/src/format.ts`: a duration formatter.
- `pwa/src/screens/Stats.tsx`: the new card and day buttons.
- Tests: `pwa/src/stats.test.ts`, `pwa/src/screens/Stats.test.tsx`, a `format` test.
- No API, backend, infra or dependency changes. `GET /api/events?days=28`, which the screen already calls, returns `duration_s` for each event.
