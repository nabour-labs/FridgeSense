# door-calibration Specification

## Purpose
Teaches the door check what open and closed look like for one camera. Covers camera snapshots, the owner's labeled door references (an image, one box around a door or drawer, and its status), the setup run that turns them into the door check's zones and threshold, how they are stored per Ring account and device, and their HTTP routes.

## Requirements

### Requirement: Camera snapshot
`POST /api/camera/snapshot` SHALL request a still for the linked account's first discovered device at the current time minus 3 s (`POST /v1/devices/{device_id}/media/image/download` with `type = "at_timestamp"`). It SHALL follow the redirect without the `Authorization` header. While face blurring is on (the default, see `face-blur-setting`), it SHALL blur every face in the still as door-event stills are blurred. While it is off, it SHALL NOT call face detection. It SHALL scale the still down to at most 960 px wide keeping its aspect ratio, and answer 200 `{"image": "<base64 JPEG>", "captured_at": "<ISO 8601 UTC>"}`. The image SHALL be at most 300,000 bytes. The snapshot SHALL NOT be stored. A still that is not ready (Ring 416 or 425) SHALL be requested once more after 2 s. When both attempts find no footage, the route SHALL fall back to the newest motion event in the device's Ring history (`GET /v1/history/devices/{device_id}/events?event_types=motion`, largest `start`) and request one still at the middle of that event (its `start` when it has no `end`); `captured_at` is then that time. The camera only records when something moves, so without this fallback a snapshot works only while someone stands in front of it.

#### Scenario: Snapshot taken
- **WHEN** the owner calls the route at 2026-10-15T19:20:10Z and Ring answers 303 with a link to a 1920×1080 JPEG with no faces
- **THEN** Ring is asked for timestamp 1792092007000, the response's `image` decodes to a 960×540 JPEG of at most 300,000 bytes, `captured_at = "2026-10-15T19:20:07.000Z"`, and nothing is written to the table or S3

#### Scenario: Face blurred in the snapshot
- **WHEN** face blurring is on and face detection reports a face at `(0.40, 0.20, 0.20, 0.30)` in the still
- **THEN** the returned image is blurred inside that face's enlarged box

#### Scenario: Snapshot while blurring is off
- **WHEN** face blurring is off and Ring returns a 1920×1080 still
- **THEN** face detection is not called and the response is 200 with a 960×540 image

#### Scenario: Snapshot from the latest motion event
- **WHEN** Ring answers 416 `MEDIA_NOT_FOUND` to both attempts at now − 3 s, and the device's history lists motion events starting 1786711000000 and 1786715596000 (ending 1786715621000)
- **THEN** one more still is requested at 1786715608500, the response is 200 with that image, and `captured_at = "2026-08-14T13:53:28.500Z"`

#### Scenario: No recent footage
- **WHEN** Ring answers 416 `MEDIA_NOT_FOUND` to both attempts and the device's history has no motion events, cannot be read, or has no still at the newest event
- **THEN** the response is 409 `{"error": "no recent footage"}`

#### Scenario: Camera or face detection unavailable
- **WHEN** Ring answers 500, the Ring token cannot be refreshed, or face blurring is on and face detection fails
- **THEN** the response is 502 `{"error": "camera unavailable"}` and no unblurred image is returned

#### Scenario: No device discovered
- **WHEN** the account is linked but no device has been discovered
- **THEN** the snapshot and every door-calibration route answer 409 `{"error": "no camera found"}`

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

### Requirement: Door zones and references record their picture's source
`POST /api/door-calibration/zones`, `PATCH /api/door-calibration/zones/{id}` (when it changes the box) and `POST /api/door-calibration/references` SHALL accept an optional `source`, either `"clip"` (a frame of a recorded event clip) or `"live"` (a live-view frame or Ring still). It defaults to `"live"`. `GET /api/door-calibration` SHALL list each zone's and reference's `source`. Zones and references stored before this change SHALL read as `"live"`.

#### Scenario: Reference from a clip
- **WHEN** the owner posts a reference with zone Z, status `closed` and `source = "clip"`
- **THEN** the response lists that reference with `source = "clip"`

#### Scenario: Source left out
- **WHEN** a zone is posted without `source`
- **THEN** it is stored and listed with `source = "live"`

#### Scenario: Unknown source
- **WHEN** `source` is `"upload"` or `3`
- **THEN** the response is 400 `{"error": "source must be clip or live"}` and nothing is stored

#### Scenario: Stored before this change
- **WHEN** the table holds a zone and a reference with no `source` field
- **THEN** `GET /api/door-calibration` lists both with `source = "live"`

#### Scenario: Rename keeps the source
- **WHEN** zone Z has `source = "clip"` and the owner sends `PATCH` with only a new name
- **THEN** Z keeps `source = "clip"`

#### Scenario: Redraw on a live picture
- **WHEN** zone Z has `source = "clip"` and the owner sends `PATCH` with a new box and no `source`
- **THEN** Z's `source` becomes `"live"`

### Requirement: Setup needs zones and references from clips
`POST /api/door-calibration/run` SHALL fail when any zone or any reference has `source = "live"`. It answers 422 with the `references` as in other setup failures, and the stored setup result stays unchanged. For a zone the error is `"zone <name> was drawn on a live picture. Redraw it on a frame from a recent clip."`. For a reference it is `"reference <n> is not from a recorded clip. Replace it with a frame from a recent clip."`, with `n` its 1-based position in `references`. Zones are checked first.

#### Scenario: Live reference refused
- **WHEN** zone "Doors" has `source = "clip"`, and its references are an open one from a clip and, listed second, a closed one with `source = "live"`
- **THEN** the response is 422 `{"error": "reference 2 is not from a recorded clip. Replace it with a frame from a recent clip.", "references": [...]}` and the stored setup is unchanged

#### Scenario: Live zone refused
- **WHEN** zone "Doors" has `source = "live"` and all its references are from clips
- **THEN** the response is 422 with `error = "zone Doors was drawn on a live picture. Redraw it on a frame from a recent clip."`

#### Scenario: Everything from clips
- **WHEN** every zone and reference has `source = "clip"` and each zone has an open and a closed reference that separate
- **THEN** setup runs as before and answers 200

### Requirement: Fridge light measured strictly in setup
Wherever setup, reference scores and self-tuning measure the `blue` feature, a pixel SHALL count as blue-lit only when `max(R,G,B) − min(R,G,B) > 100`, `max(R,G,B) > 120` and `B − max(R,G) > 60`, the same rule the door check uses. This replaces the `blue` thresholds given in "Run setup". The `color`, `brightness` and `change` features are unchanged.

#### Scenario: Daylit steel is not fridge light
- **WHEN** a zone of a closed reference is grey except a `(110,150,200)` area covering 30% of it
- **THEN** that reference's `blue` value is 0.0

#### Scenario: Fridge interior is fridge light
- **WHEN** a zone of an open reference is grey except a `(40,90,200)` block covering 10% of it
- **THEN** that reference's `blue` value is about 0.1

### Requirement: Fridge light preferred in setup
When choosing a zone's feature, setup SHALL use `blue` whenever `blue` separates the zone's open and closed references by at least the minimum margin of 0.01, even if another feature has a larger margin. Only when `blue` does not separate does the zone use the feature with the largest margin, with ties in the order color, change, brightness. Re-tuning from event samples SHALL choose the same way.

#### Scenario: Blue wins over a larger change margin
- **WHEN** in a zone `blue` separates with margin 0.04 and `change` separates with margin 0.09
- **THEN** that zone's feature is `blue`, with the threshold at the midpoint of `blue`'s two values

#### Scenario: Blue too close to call
- **WHEN** in a zone `blue` separates with margin 0.005 and `change` with margin 0.09
- **THEN** that zone's feature is `change`

#### Scenario: Drawer without fridge light
- **WHEN** a drawer zone's open and closed references both have a `blue` value of 0.0, and `change` separates with margin 0.2
- **THEN** that zone's feature is `change`

#### Scenario: Re-tune keeps blue
- **WHEN** the owner's references plus the event samples separate a zone on `blue` by 0.03 and on `brightness` by 0.2
- **THEN** the tuned rule for that zone uses `blue`
