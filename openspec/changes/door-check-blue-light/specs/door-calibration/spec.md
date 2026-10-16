## MODIFIED Requirements

### Requirement: Run setup
`POST /api/door-calibration/run` SHALL work out, for each zone, which signal tells open from closed and at what level, store the result as the device's setup result, and answer 200 with the `GET /api/door-calibration` body:

1. **Zones:** the references' boxes, in the order they were added, are grouped. A box joins the first group whose bounding box it overlaps with intersection-over-union ≥ 0.3, otherwise it starts a new group. Each group's zone is the bounding box of its boxes, rounded to 3 places, and each reference belongs to its box's zone. More than 6 groups SHALL fail.
2. **Features:** for a zone of an image, four values are measured, each from 0 to 1:
   - `blue`: the fraction of pixels that are colorful and blue-lit, by the door check's rule (`max − min > 60`, `max > 100` and `B − max(R,G) > 20`).
   - `color`: the fraction of colorful pixels, by the door check's rule (`max − min > 60` and `max > 100`).
   - `brightness`: the mean luminance divided by 255.
   - `change`: the mean absolute difference, over every channel, between the zone scaled to 32×32 RGB and the zone's *baseline*, divided by 255. The baseline is the per-pixel mean of the zone's closed references, each scaled to 32×32.
3. **Choice:** for each zone and feature, with `O` the values of the zone's open references and `C` of its closed ones:
   - If `min(O) > max(C)`, the direction is `above` and `margin = min(O) − max(C)`.
   - If `max(O) < min(C)`, the direction is `below` and `margin = min(C) − max(O)`.
   - Otherwise the feature does not separate.

   The threshold is the midpoint of the two values that set the margin. The zone uses the feature with the largest margin, with ties going in the order blue, color, change, brightness. A margin below 0.01 counts as not separating. Thresholds and margins are rounded to 4 places.

On failure the stored setup result SHALL be unchanged, and the response SHALL be 422 with an `error` and the `references` with their `score` set to the color value from this attempt.

#### Scenario: Setup from one open and one closed reference
- **WHEN** both references have box `{"x": 0, "y": 0, "width": 0.5, "height": 1}`, the open one is a 200×100 grey `(128,128,128)` still with a `(40,90,200)` block covering 10% of the left half, and the closed one is plain grey
- **THEN** the response has one zone `{"x": 0, "y": 0, "width": 0.5, "height": 1, "feature": "blue", "direction": "above", "threshold": 0.05, "margin": 0.1}` (±0.005), `stale = false`, and scores 0.1 and 0.0

#### Scenario: Brightness chosen when there is no color
- **WHEN** one zone has two closed references, plain `(100,100,100)` and one whose left half is `(40,40,40)` and right half `(160,160,160)` (someone in front), and one open reference that is plain `(200,200,200)`
- **THEN** that zone's feature is `brightness`, direction `above`, with a margin of about 0.39 and a threshold of about 0.59

#### Scenario: Change chosen when brightness is the same
- **WHEN** a zone's closed reference is plain `(128,128,128)` and its open reference has its left half `(40,40,40)` and right half `(216,216,216)`
- **THEN** that zone's feature is `change`, direction `above`, with a margin of about 0.35

#### Scenario: Darker when open
- **WHEN** a zone's closed references are plain `(220,220,220)` and one whose left half is `(180,180,180)` and right half `(240,240,240)`, and its open reference is plain `(90,90,90)`, with no color in any
- **THEN** that zone's feature is `brightness` with direction `below`, a margin of about 0.47 and a threshold of about 0.59

#### Scenario: Overlapping boxes become one zone
- **WHEN** the references' boxes are `{0.1, 0.1, 0.3, 0.4}`, `{0.12, 0.1, 0.3, 0.4}` and `{0.5, 0.6, 0.1, 0.1}` (x, y, width, height)
- **THEN** the zones are `{"x": 0.1, "y": 0.1, "width": 0.32, "height": 0.4}` and `{"x": 0.5, "y": 0.6, "width": 0.1, "height": 0.1}`, in that order

#### Scenario: Missing a status
- **WHEN** there are no references, or a zone's references are all `closed` or all `open`
- **THEN** the response is 422 with `{"error": "zone 1 needs an open and a closed reference", "references": [...]}` (naming the first such zone; with no references, zone 1), and the stored setup is unchanged

#### Scenario: Open and closed overlap
- **WHEN** a zone's open reference is grey with a `(40,90,200)` block covering 0.5% of the zone and its closed reference is plain grey, so no feature has a margin of at least 0.01
- **THEN** the response is 422 `{"error": "zone 1: open and closed references overlap", "references": [...]}` and the stored setup is unchanged

#### Scenario: Too many zones
- **WHEN** the references' boxes form 7 separate groups
- **THEN** the response is 422 `{"error": "at most 6 separate zones", "references": [...]}`

#### Scenario: Blue preferred over color on a tie
- **WHEN** a zone's open reference has a `(40,90,200)` block covering 10% of the zone and its closed reference is plain grey, so `blue` and `color` both separate with a margin of 0.1
- **THEN** that zone's feature is `blue`

#### Scenario: Color chosen when the open reference is not blue
- **WHEN** a zone's open reference has a `(200,60,40)` block covering 10% of the zone and its closed reference is plain grey
- **THEN** that zone's feature is `color`, since `blue` measures 0 on both and does not separate
