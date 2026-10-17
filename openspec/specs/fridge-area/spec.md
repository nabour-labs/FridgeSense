# fridge-area Specification

## Purpose
Stores the owner's box around the fridge in the camera's view, per Ring account and device, and serves it over the HTTP API so stills can later be cropped to the fridge before analysis.

## Requirements

### Requirement: Read the fridge area
`GET /api/fridge-area` SHALL return 200 for the account's first discovered device with this shape:

```json
{
  "device_id": "<device id>",
  "area": {"image": "<base64 JPEG>", "box": {"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9},
           "updated_at": "<ISO 8601 UTC>"} | null
}
```

`area` SHALL be null when no fridge area was saved for the device. Owner and viewer tokens SHALL both be accepted. With no discovered device the response SHALL be 409 `{"error": "no camera found"}`.

#### Scenario: No fridge area yet
- **WHEN** no fridge area was saved for the device
- **THEN** the response is 200 with the device's `device_id` and `area = null`

#### Scenario: Viewer reads the fridge area
- **WHEN** a viewer calls `GET /api/fridge-area` after the owner saved an area
- **THEN** the response is 200 with that area's image, box and `updated_at`

#### Scenario: Fridge area needs a camera
- **WHEN** the account has no discovered device
- **THEN** `GET /api/fridge-area` and `PUT /api/fridge-area` answer 409 `{"error": "no camera found"}`

#### Scenario: Fridge area needs a token
- **WHEN** `GET /api/fridge-area` is called without a token
- **THEN** the response is 401 `{"error": "sign in"}`

### Requirement: Save the fridge area
`PUT /api/fridge-area` with `{"image": "<base64 JPEG>", "box": {"x", "y", "width", "height"}}` SHALL store the fridge area for the account's first discovered device, keyed by Ring account and device ID, replacing any earlier one, and answer 200 with the `GET /api/fridge-area` body. The image SHALL be a JPEG of at most 300,000 bytes. The box SHALL be fractions of the image with `x ≥ 0`, `y ≥ 0`, `width ≥ 0.02`, `height ≥ 0.02`, `x + width ≤ 1` and `y + height ≤ 1`. Only the owner SHALL be able to save. Saving SHALL NOT change door detection, stills or analysis.

#### Scenario: Fridge area saved
- **WHEN** the owner puts a 960×540 JPEG with box `{"x": 0.2, "y": 0.05, "width": 0.5, "height": 0.9}` at 2026-10-16T01:00:00Z
- **THEN** the response is 200 with that image, that box and `updated_at = "2026-10-16T01:00:00.000Z"`, and a following `GET /api/fridge-area` returns the same area

#### Scenario: Saving again replaces the area
- **WHEN** an area is saved and the owner saves another with box `{"x": 0.1, "y": 0, "width": 0.6, "height": 1}`
- **THEN** `GET /api/fridge-area` returns only the second box and image

#### Scenario: Invalid fridge area rejected
- **WHEN** the image is a PNG or over 300,000 bytes, or the box has `x = 0.9` with `width = 0.2`, `width = 0.01` or a missing `height`
- **THEN** the response is 400 with `{"error": "image must be a JPEG of at most 300 KB"}` or `{"error": "box must be inside the image and at least 2% wide and tall"}`, and the stored area is unchanged

#### Scenario: Viewer cannot save the fridge area
- **WHEN** a viewer calls `PUT /api/fridge-area` with a valid body
- **THEN** the response is 403 `{"error": "read-only"}` and nothing is stored

#### Scenario: Fridge area kept per device
- **WHEN** areas are stored for devices `dev-1` and `dev-2` of the same account
- **THEN** loading the area for `dev-1` returns only `dev-1`'s box
