## ADDED Requirements

### Requirement: Daily open-time stats
The Stats screen SHALL show an "Open time" card with the average, longest and shortest `duration_s` of the door events that opened on one selected local day (device time zone). The card SHALL offer one button for each of the last 7 days, oldest first, labelled with the short weekday except the last, which is labelled "Today"; the selected button SHALL be marked pressed, and today SHALL be selected when the screen opens. The average SHALL be rounded to the nearest whole second. Each value SHALL read "N s" below 60 seconds and "M m SS s" from 60 seconds up, with seconds padded to 2 digits. A day with no openings SHALL show "–" for all three values and the text "No openings".

#### Scenario: Today's open times
- **WHEN** today has 3 openings of 20 s, 30 s and 40 s and yesterday has 2 openings of 25 s and 35 s
- **THEN** the "Open time" card has "Today" pressed and shows Average "30 s", Longest "40 s" and Shortest "20 s"

#### Scenario: Pick another day
- **WHEN** the user taps the button for yesterday in the same data
- **THEN** that button is pressed, "Today" is not, and the card shows Average "30 s", Longest "35 s" and Shortest "25 s"

#### Scenario: Seven day buttons
- **WHEN** the Stats screen loads
- **THEN** the "Open time" card has 7 day buttons for the last 7 local days, oldest first, the last one labelled "Today"

#### Scenario: Minutes and seconds
- **WHEN** durations are formatted
- **THEN** 0 reads "0 s", 45 reads "45 s", 59 reads "59 s", 60 reads "1 m 00 s", 65 reads "1 m 05 s" and 600 reads "10 m 00 s"

#### Scenario: Long opening on the card
- **WHEN** today has openings of 65 s and 20 s
- **THEN** the card shows Longest "1 m 05 s", Shortest "20 s" and Average "43 s"

#### Scenario: Average rounded
- **WHEN** a day has openings of 20 s and 25 s
- **THEN** the average is 23 s

#### Scenario: Single opening
- **WHEN** a day has one opening of 18 s
- **THEN** Average, Longest and Shortest all show "18 s"

#### Scenario: Day without openings
- **WHEN** the selected day has no openings
- **THEN** Average, Longest and Shortest each show "–" and the card shows "No openings", without errors

#### Scenario: Open time in local days
- **WHEN** an event opened at 2026-10-15T02:30:00Z with `duration_s` 50 and the device is in America/Vancouver (UTC−7)
- **THEN** it counts toward the Oct 14 open-time stats and not Oct 15
