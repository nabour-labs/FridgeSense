## REMOVED Requirements

### Requirement: Stats screen
**Reason**: The 24-cell hour strip is replaced by a weekday × hour heatmap over 28 days.
**Migration**: See "Door-opening stats" below.

## ADDED Requirements

### Requirement: Door-opening stats
The Stats screen SHALL request the last 28 days of door events and compute everything in the device's time zone. From the last 7 days it SHALL show opens per day as a bar chart with today's bar highlighted, today's number of opens, the number of opens in the last 7 days, and the average time the door stayed open. From all 28 days it SHALL show an "Opens by day and hour" heatmap: 7 rows (Sunday to Saturday) by 24 columns (hours 00–23), each cell shaded in one of 5 levels by how many openings fell in that weekday and hour, with a "Less … More" legend.

#### Scenario: Stats from events
- **WHEN** the last 7 days have 3 openings today (20 s, 30 s and 40 s) and 2 yesterday (25 s and 35 s)
- **THEN** "Today" shows 3, the per-day chart has 7 bars with 3 for today and 2 for yesterday, and the average open time shows "30 s"

#### Scenario: Today marked
- **WHEN** the per-day counts are computed
- **THEN** only the last day (today) has `isToday` true

#### Scenario: Four weeks requested
- **WHEN** the Stats screen loads
- **THEN** it calls `events(28)`

#### Scenario: Older events only in the heatmap
- **WHEN** the events are one opening today and one opening 10 days ago
- **THEN** "Last 7 days" shows 1 and the heatmap counts both openings

#### Scenario: Day and hour heatmap
- **WHEN** there are 2 openings on Mondays at 19:00 and none on Wednesdays at 03:00
- **THEN** the "Opens by day and hour" figure has 168 cells, including "Mon 19:00, 2 opens" and "Wed 03:00, 0 opens", and shows a legend from "Less" to "More"

#### Scenario: Heat levels
- **WHEN** the busiest cell has 8 opens
- **THEN** a cell with 0 opens is level 0, 1 open is level 1, 4 opens is level 2, 5 opens is level 3, and 8 opens is level 4

#### Scenario: Local time zone
- **WHEN** an event opened at 2026-10-15T02:30:00Z (a Thursday in UTC) and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward Oct 14, hour 19, and the Wednesday row of the heatmap

#### Scenario: No openings yet
- **WHEN** there are no events in the last 28 days
- **THEN** the screen shows zeros, the bar chart shows empty bars, and every heatmap cell is level 0, without errors
