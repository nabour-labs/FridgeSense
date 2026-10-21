# Proposal

## Why

When nobody has opened the fridge yet today, the Activity screen opens on an empty day and the user has to dig back with the date picker to find the last openings.

## What Changes

- When the Activity screen opens and today has no door openings, it starts on the most recent day in the last 31 days that has one. The API caps a range at 31 days, so one request (`limit=1`, newest first) finds it.
- If there are none in that window, or the lookup fails, it stays on today, as before.
- Picking a day by hand is unchanged.

## Capabilities

### Modified Capabilities

- `inventory-app`: the Activity screen's default day.
