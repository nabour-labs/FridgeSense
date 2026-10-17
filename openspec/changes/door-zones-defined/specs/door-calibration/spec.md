# Spec Delta

## ADDED Requirements

### Requirement: Define door zones
`POST /api/door-calibration/zones` with `{"name": "<1–30 chars>", "box": {"x", "y", "width", "height"}}` SHALL store a door zone for the device and answer 200 with the `GET /api/door-calibration` body. The box follows the reference box rules. A device SHALL hold at most 6 zones. `PATCH /api/door-calibration/zones/{id}` with `name`, `box` or both SHALL change that zone. `DELETE /api/door-calibration/zones/{id}` SHALL remove it and its references. Neither SHALL change the stored setup result. Adding, changing or deleting a zone SHALL mark setup stale.

#### Scenario: Zone added
- **WHEN** the owner posts `{"name": "Freezer drawer", "box": {"x": 0.38, "y": 0.65, "width": 0.2, "height": 0.25}}`
- **THEN** the response's `zones` lists it last with a non-empty `id`, that name and box, `open = 0` and `closed = 0`

#### Scenario: Invalid zone rejected
- **WHEN** the name is empty, only spaces or over 30 characters, or the box has `x = 0.9` with `width = 0.2`
- **THEN** the response is 400 with `{"error": "name must be 1 to 30 characters"}` or `{"error": "box must be inside the image and at least 2% wide and tall"}`, and nothing is stored

#### Scenario: Zone limit
- **WHEN** 6 zones exist and the owner adds another
- **THEN** the response is 409 `{"error": "at most 6 door zones"}`

#### Scenario: Zone redrawn
- **WHEN** setup ran, and the owner patches zone Z with box `{"x": 0.36, "y": 0.3, "width": 0.25, "height": 0.4}`
- **THEN** Z has the new box and the same name, every reference of Z is listed with the new box, and `setup.stale` is true

#### Scenario: Zone deleted with its references
- **WHEN** zone Z has 2 references and the owner deletes Z
- **THEN** Z and its 2 references are no longer listed, and patching or deleting an unknown zone id answers 404 `{"error": "not found"}`

## MODIFIED Requirements

### Requirement: Read the door setup
`GET /api/door-calibration` SHALL return 200 for the account's first discovered device with this shape:

```json
{
  "device_id": "<device id>",
  "zones": [{"id": "<id>", "name": "Fridge doors", "box": {"x": 0, "y": 0, "width": 0.5, "height": 1},
             "open": 1, "closed": 2}],
  "references": [{"id": "<id>", "zone_id": "<zone id>", "image": "<base64 JPEG>",
                  "box": {"x": 0, "y": 0, "width": 0.5, "height": 1},
                  "status": "open" | "closed", "score": 0.1 | null, "created_at": "<ISO 8601 UTC>"}],
  "setup": {"zones": [{"id", "name", "x", "y", "width", "height", "feature": "blue" | "color" | "brightness" | "change",
                        "direction": "above" | "below", "threshold": 0.05, "margin": 0.1}],
            "ran_at": "<ISO 8601 UTC>", "stale": false} | null,
  "defaults": {"zones": [{"x", "y", "width", "height"}], "threshold": 0.02}
}
```

Zones and references SHALL be listed oldest first. A zone's `open` and `closed` SHALL count its references. A reference's `box` SHALL be its zone's current box. Its `score` SHALL be its zone's setup feature on its image, rounded to 3 places, or null when there is no setup or the setup has no zone with its `zone_id`. References with no zone SHALL NOT be listed. `setup.stale` SHALL be true when a zone or reference changed after `ran_at`. `defaults` SHALL be what the door check uses without a setup result (`DOOR_ZONES`/`DOOR_THRESHOLD`, else the built-in defaults). Owner and viewer tokens SHALL both be accepted.

#### Scenario: Nothing set up yet
- **WHEN** no zones or references were added and setup never ran, and `DOOR_ZONES` and `DOOR_THRESHOLD` are unset
- **THEN** the response has `zones = []`, `references = []`, `setup = null`, and `defaults` with the two built-in zones and `threshold = 0.02`

#### Scenario: Setup marked stale
- **WHEN** setup ran and then the owner added a reference
- **THEN** `setup.stale` is true, and the new reference's `score` is computed with its zone's existing setup feature

#### Scenario: Reference of a zone added after setup
- **WHEN** setup ran with zone Z1, and the owner then added zone Z2 and a reference to Z2
- **THEN** that reference's `score` is null

#### Scenario: Old references without a zone
- **WHEN** the table holds a door reference stored with a `box` and no `zone_id`
- **THEN** it is not in `references`, and it is not counted in any zone's `open` or `closed`

#### Scenario: No token
- **WHEN** `GET /api/door-calibration` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

### Requirement: Add and delete door references
`POST /api/door-calibration/references` with `{"image": "<base64 JPEG>", "zone_id": "<zone id>", "status": "open" | "closed"}` SHALL store a door reference for that zone and answer 200 with the `GET /api/door-calibration` body. The image SHALL be a JPEG of at most 300,000 bytes. The zone SHALL be one of the device's zones. A device SHALL hold at most 24 references; references with no zone do not count. `DELETE /api/door-calibration/references/{id}` SHALL remove one and answer 200 with the same body. Neither route SHALL change the stored setup result.

#### Scenario: Reference added
- **WHEN** zone Z has box `{"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}`, and the owner posts a 960×540 JPEG with `zone_id` Z and status `open`
- **THEN** the response lists that reference with a non-empty `id`, `zone_id` Z, Z's box, `status = "open"` and an ISO 8601 `created_at`, and Z's `open` is 1

#### Scenario: Invalid reference rejected
- **WHEN** the image is a PNG or over 300,000 bytes, or the status is `ajar`
- **THEN** the response is 400 with `{"error": "image must be a JPEG of at most 300 KB"}` or `{"error": "status must be open or closed"}`, and nothing is stored

#### Scenario: Unknown zone
- **WHEN** `zone_id` is missing or is not one of the device's zones
- **THEN** the response is 400 `{"error": "pick a door zone"}` and nothing is stored

#### Scenario: Reference limit
- **WHEN** 24 references exist and the owner adds another
- **THEN** the response is 409 `{"error": "at most 24 door references"}`

#### Scenario: Reference deleted
- **WHEN** the owner deletes an existing reference
- **THEN** it is no longer listed, and deleting an unknown id answers 404 `{"error": "not found"}`

### Requirement: Run setup
`POST /api/door-calibration/run` SHALL work out, for each zone, which signal tells open from closed and at what level, store the result as the device's setup result, and answer 200 with the `GET /api/door-calibration` body:

1. **Zones:** the device's defined zones, in the order they were added, each with its `id`, `name` and box. Each reference belongs to the zone named by its `zone_id`. References with no zone are ignored.
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
- **WHEN** zone "Doors" has box `{"x": 0, "y": 0, "width": 0.5, "height": 1}`, its open reference is a 200×100 grey `(128,128,128)` still with a `(40,90,200)` block covering 10% of the left half, and its closed one is plain grey
- **THEN** the response has one setup zone with that zone's `id`, `name = "Doors"` and `{"x": 0, "y": 0, "width": 0.5, "height": 1, "feature": "blue", "direction": "above", "threshold": 0.05, "margin": 0.1}` (±0.005), `stale = false`, and scores 0.1 and 0.0

#### Scenario: Brightness chosen when there is no color
- **WHEN** one zone has two closed references, plain `(100,100,100)` and one whose left half is `(40,40,40)` and right half `(160,160,160)` (someone in front), and one open reference that is plain `(200,200,200)`
- **THEN** that zone's feature is `brightness`, direction `above`, with a margin of about 0.39 and a threshold of about 0.59

#### Scenario: Change chosen when brightness is the same
- **WHEN** a zone's closed reference is plain `(128,128,128)` and its open reference has its left half `(40,40,40)` and right half `(216,216,216)`
- **THEN** that zone's feature is `change`, direction `above`, with a margin of about 0.35

#### Scenario: Darker when open
- **WHEN** a zone's closed references are plain `(220,220,220)` and one whose left half is `(180,180,180)` and right half `(240,240,240)`, and its open reference is plain `(90,90,90)`, with no color in any
- **THEN** that zone's feature is `brightness` with direction `below`, a margin of about 0.47 and a threshold of about 0.59

#### Scenario: One setup zone per defined zone
- **WHEN** zones "Doors" `{0.35, 0.32, 0.24, 0.38}` and "Drawer" `{0.37, 0.64, 0.22, 0.28}` (x, y, width, height) were added in that order, each with one open and one closed reference that separate
- **THEN** the setup has exactly two zones, "Doors" then "Drawer", with exactly those boxes

#### Scenario: Overlapping boxes become one zone
- **WHEN** zones "Doors" `{0.35, 0.32, 0.24, 0.38}` and "Drawer" `{0.37, 0.64, 0.22, 0.28}` overlap, and each has one open and one closed reference that separate
- **THEN** the setup still has two zones with exactly those boxes; zones are never merged

#### Scenario: Too many zones
- **WHEN** the table holds 7 zones for the device (written directly, since the API caps zones at 6)
- **THEN** the response is 422 `{"error": "at most 6 door zones", "references": [...]}` and the stored setup is unchanged

#### Scenario: References in one zone are not regrouped
- **WHEN** zone "Drawer" has a closed reference and an open reference that the owner took with the drawer in very different places
- **THEN** both are measured inside "Drawer"'s box, and setup does not answer that a zone is missing a status

#### Scenario: No zones
- **WHEN** the device has no zones
- **THEN** the response is 422 with `{"error": "add a door zone first", "references": []}` and the stored setup is unchanged

#### Scenario: Missing a status
- **WHEN** zone "Doors" has an open and a closed reference, and zone "Freezer drawer" has only closed references, or none
- **THEN** the response is 422 with `{"error": "Freezer drawer needs an open and a closed reference", "references": [...]}` (naming the first such zone), and the stored setup is unchanged

#### Scenario: Open and closed overlap
- **WHEN** zone "Doors"'s open reference is grey with a `(40,90,200)` block covering 0.5% of the zone and its closed reference is plain grey, so no feature has a margin of at least 0.01
- **THEN** the response is 422 `{"error": "Doors: open and closed references overlap", "references": [...]}` and the stored setup is unchanged

#### Scenario: Old references ignored
- **WHEN** zone "Doors" has one open and one closed reference, and the table also holds an old open reference with a box and no `zone_id`
- **THEN** setup succeeds using only the two zone references

#### Scenario: Blue preferred over color on a tie
- **WHEN** a zone's open reference has a `(40,90,200)` block covering 10% of the zone and its closed reference is plain grey, so `blue` and `color` both separate with a margin of 0.1
- **THEN** that zone's feature is `blue`

#### Scenario: Color chosen when the open reference is not blue
- **WHEN** a zone's open reference has a `(200,60,40)` block covering 10% of the zone and its closed reference is plain grey
- **THEN** that zone's feature is `color`, since `blue` measures 0 on both and does not separate

### Requirement: Door-setup writes are owner-only and per device
The snapshot route and the door-calibration write routes SHALL follow the existing auth rules: they need a valid token, a viewer token SHALL get 403 `{"error": "read-only"}`, and they need a linked account (otherwise 409). Zones, references and the setup result SHALL be stored and read under the Ring `account_id` and `device_id`.

#### Scenario: Viewer cannot change the setup
- **WHEN** a viewer token calls `POST /api/camera/snapshot`, `POST /api/door-calibration/zones`, `PATCH /api/door-calibration/zones/{id}`, `DELETE /api/door-calibration/zones/{id}`, `POST /api/door-calibration/references`, `DELETE /api/door-calibration/references/{id}` or `POST /api/door-calibration/run`
- **THEN** each response is 403 `{"error": "read-only"}`, no Ring request is made, and nothing is stored

#### Scenario: Setup kept per device
- **WHEN** setup ran for device D1 of account A, and a motion event arrives for device D2 of account A
- **THEN** the door check for D2 uses the defaults, not D1's setup

#### Scenario: Zones kept per device
- **WHEN** device D1 of account A has zone Z, and the owner posts a reference with `zone_id` Z while D2 is the first discovered device
- **THEN** the response is 400 `{"error": "pick a door zone"}`
