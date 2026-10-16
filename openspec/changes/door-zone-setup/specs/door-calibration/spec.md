# Spec Delta

## Purpose
Teaches the door check what open and closed look like for one camera. Covers camera snapshots, the owner's labeled door references (an image, one box around a door or drawer, and its status), the setup run that turns them into the door check's zones and threshold, how they are stored per Ring account and device, and their HTTP routes.

## ADDED Requirements

### Requirement: Camera snapshot
`POST /api/camera/snapshot` SHALL request a still for the linked account's first discovered device at the current time minus 3 s (`POST /v1/devices/{device_id}/media/image/download` with `type = "at_timestamp"`). It SHALL follow the redirect without the `Authorization` header, blur every face in the still as door-event stills are blurred, scale it down to at most 960 px wide keeping its aspect ratio, and answer 200 `{"image": "<base64 JPEG>", "captured_at": "<ISO 8601 UTC>"}`. The image SHALL be at most 300,000 bytes. The snapshot SHALL NOT be stored. A still that is not ready (Ring 416 or 425) SHALL be requested once more after 2 s.

#### Scenario: Snapshot taken
- **WHEN** the owner calls the route at 2026-10-15T19:20:10Z and Ring answers 303 with a link to a 1920×1080 JPEG with no faces
- **THEN** Ring is asked for timestamp 1792092007000, the response's `image` decodes to a 960×540 JPEG of at most 300,000 bytes, `captured_at = "2026-10-15T19:20:07.000Z"`, and nothing is written to the table or S3

#### Scenario: Face blurred in the snapshot
- **WHEN** face detection reports a face at `(0.40, 0.20, 0.20, 0.30)` in the still
- **THEN** the returned image is blurred inside that face's enlarged box

#### Scenario: No recent footage
- **WHEN** Ring answers 416 `MEDIA_NOT_FOUND` to both attempts
- **THEN** the response is 409 `{"error": "no recent footage"}`

#### Scenario: Camera or face detection unavailable
- **WHEN** Ring answers 500, the Ring token cannot be refreshed, or face detection fails
- **THEN** the response is 502 `{"error": "camera unavailable"}` and no unblurred image is returned

#### Scenario: No device discovered
- **WHEN** the account is linked but no device has been discovered
- **THEN** the snapshot and every door-calibration route answer 409 `{"error": "no camera found"}`

### Requirement: Read the door setup
`GET /api/door-calibration` SHALL return 200 for the account's first discovered device with this shape:

```json
{
  "device_id": "<device id>",
  "references": [{"id": "<id>", "image": "<base64 JPEG>", "box": {"x": 0, "y": 0, "width": 0.5, "height": 1},
                  "status": "open" | "closed", "score": 0.1 | null, "created_at": "<ISO 8601 UTC>"}],
  "setup": {"zones": [{"x", "y", "width", "height"}], "threshold": 0.05, "closed_max": 0.0, "open_min": 0.1,
            "ran_at": "<ISO 8601 UTC>", "stale": false} | null,
  "defaults": {"zones": [{"x", "y", "width", "height"}], "threshold": 0.02}
}
```

References SHALL be listed oldest first. Each reference's `score` SHALL be its door-check score (the highest colorful-pixel fraction over the setup's zones), rounded to 3 places, or null when there is no setup result. `setup.stale` SHALL be true when a reference was added or deleted after `ran_at`. `defaults` SHALL be what the door check uses without a setup result (`DOOR_ZONES`/`DOOR_THRESHOLD`, else the built-in defaults). Owner and viewer tokens SHALL both be accepted.

#### Scenario: Nothing set up yet
- **WHEN** no references were added and setup never ran, and `DOOR_ZONES` and `DOOR_THRESHOLD` are unset
- **THEN** the response has `references = []`, `setup = null`, and `defaults` with the two built-in zones and `threshold = 0.02`

#### Scenario: Setup marked stale
- **WHEN** setup ran and then the owner added a reference
- **THEN** `setup.stale` is true, and the new reference's `score` is computed with the existing setup's zones

#### Scenario: No token
- **WHEN** `GET /api/door-calibration` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

### Requirement: Add and delete door references
`POST /api/door-calibration/references` with `{"image": "<base64 JPEG>", "box": {"x", "y", "width", "height"}, "status": "open" | "closed"}` SHALL store a door reference for the device and answer 200 with the `GET /api/door-calibration` body. The image SHALL be a JPEG of at most 300,000 bytes. The box SHALL be fractions of the image with `x ≥ 0`, `y ≥ 0`, `width ≥ 0.02`, `height ≥ 0.02`, `x + width ≤ 1` and `y + height ≤ 1`. A device SHALL hold at most 12 references. `DELETE /api/door-calibration/references/{id}` SHALL remove one and answer 200 with the same body. Neither route SHALL change the stored setup result.

#### Scenario: Reference added
- **WHEN** the owner posts a 960×540 JPEG, box `{"x": 0.38, "y": 0.32, "width": 0.21, "height": 0.30}` and status `open`
- **THEN** the response lists that reference with a non-empty `id`, the box, `status = "open"` and an ISO 8601 `created_at`

#### Scenario: Invalid reference rejected
- **WHEN** the image is a PNG or over 300,000 bytes, or the box has `x = 0.9` with `width = 0.2`, `width = 0.01` or a missing `height`, or the status is `ajar`
- **THEN** the response is 400 with `{"error": "image must be a JPEG of at most 300 KB"}`, `{"error": "box must be inside the image and at least 2% wide and tall"}` or `{"error": "status must be open or closed"}`, and nothing is stored

#### Scenario: Reference limit
- **WHEN** 12 references exist and the owner adds another
- **THEN** the response is 409 `{"error": "at most 12 door references"}`

#### Scenario: Reference deleted
- **WHEN** the owner deletes an existing reference
- **THEN** it is no longer listed, and deleting an unknown id answers 404 `{"error": "not found"}`

### Requirement: Run setup
`POST /api/door-calibration/run` SHALL compute the zones and threshold from the device's references, store them as the device's setup result, and answer 200 with the `GET /api/door-calibration` body:

1. **Zones:** the references' boxes, in the order they were added, are grouped. A box joins the first group whose bounding box it overlaps with intersection-over-union ≥ 0.3, otherwise it starts a new group. Each group's zone is the bounding box of its boxes, rounded to 3 places. More than 6 groups SHALL fail.
2. **Scores:** each reference's score is the highest colorful-pixel fraction over the zones, by the door check's rule.
3. **Threshold:** with `closed_max` the highest closed score and `open_min` the lowest open score, the threshold is `(closed_max + open_min) / 2` rounded to 3 places, and at least 0.005. It SHALL fail when `open_min ≤ closed_max`.

On failure the stored setup result SHALL be unchanged, and the response SHALL be 422 with an `error` and the `references` with the scores from this attempt.

#### Scenario: Setup from one open and one closed reference
- **WHEN** both references have box `{"x": 0, "y": 0, "width": 0.5, "height": 1}`, the open one is a 200×100 grey `(128,128,128)` still with a `(40,90,200)` block covering 10% of the left half, and the closed one is plain grey
- **THEN** the response has `setup.zones = [{"x": 0, "y": 0, "width": 0.5, "height": 1}]`, `threshold = 0.05`, `closed_max = 0.0`, `open_min = 0.1`, `stale = false`, and scores 0.1 and 0.0

#### Scenario: Overlapping boxes become one zone
- **WHEN** the references' boxes are `{0.1, 0.1, 0.3, 0.4}`, `{0.12, 0.1, 0.3, 0.4}` and `{0.5, 0.6, 0.1, 0.1}` (x, y, width, height)
- **THEN** `setup.zones` is `[{"x": 0.1, "y": 0.1, "width": 0.32, "height": 0.4}, {"x": 0.5, "y": 0.6, "width": 0.1, "height": 0.1}]`

#### Scenario: Threshold floor
- **WHEN** the closed references score 0.0 and the only open reference scores 0.006
- **THEN** `threshold = 0.005`

#### Scenario: Missing a status
- **WHEN** every reference is `closed`, or every reference is `open`, or there are none
- **THEN** the response is 422 `{"error": "add at least one open and one closed reference", "references": [...]}` and the stored setup is unchanged

#### Scenario: Open and closed overlap
- **WHEN** a closed reference scores 0.08 and an open reference scores 0.05
- **THEN** the response is 422 `{"error": "open and closed references overlap", "references": [...]}` with those scores, and the stored setup is unchanged

#### Scenario: Too many zones
- **WHEN** the references' boxes form 7 separate groups
- **THEN** the response is 422 `{"error": "at most 6 separate zones", "references": [...]}`

### Requirement: Door-setup writes are owner-only and per device
The snapshot route and the door-calibration write routes SHALL follow the existing auth rules: they need a valid token, a viewer token SHALL get 403 `{"error": "read-only"}`, and they need a linked account (otherwise 409). References and the setup result SHALL be stored and read under the Ring `account_id` and `device_id`.

#### Scenario: Viewer cannot change the setup
- **WHEN** a viewer token calls `POST /api/camera/snapshot`, `POST /api/door-calibration/references`, `DELETE /api/door-calibration/references/{id}` or `POST /api/door-calibration/run`
- **THEN** each response is 403 `{"error": "read-only"}`, no Ring request is made, and nothing is stored

#### Scenario: Setup kept per device
- **WHEN** setup ran for device D1 of account A, and a motion event arrives for device D2 of account A
- **THEN** the door check for D2 uses the defaults, not D1's setup
