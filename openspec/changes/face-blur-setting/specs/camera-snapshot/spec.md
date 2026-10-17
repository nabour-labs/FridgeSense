# Spec Delta

## MODIFIED Requirements

### Requirement: Blur a live frame
`POST /api/camera/frame` SHALL take `{"image": "<base64 JPEG>"}` and scale it down to at most 960 px wide, keeping its aspect ratio. While face blurring is on (the default, see `face-blur-setting`), it SHALL blur every face in the frame as door-event stills are blurred. While face blurring is off, it SHALL NOT call face detection. It SHALL answer 200 `{"image": "<base64 JPEG>", "captured_at": "<ISO 8601 UTC>"}`, where `captured_at` is the time the request was handled. The returned image SHALL be at most 300,000 bytes. Neither the frame nor the result SHALL be stored.

#### Scenario: Frame blurred and returned
- **WHEN** the owner sends a 1920×1080 JPEG with no faces at 2026-10-15T19:20:10Z
- **THEN** the response is 200, `image` decodes to a 960×540 JPEG of at most 300,000 bytes, `captured_at = "2026-10-15T19:20:10.000Z"`, and nothing is written to the table or S3

#### Scenario: Face blurred in the frame
- **WHEN** face blurring is on and face detection reports a face at `(0.40, 0.20, 0.20, 0.30)` in the frame
- **THEN** the returned image is blurred inside that face's enlarged box

#### Scenario: Frame while blurring is off
- **WHEN** face blurring is off and the owner sends a 1920×1080 JPEG
- **THEN** face detection is not called and the response is 200 with a 960×540 image

#### Scenario: Small frame kept at its size
- **WHEN** the owner sends a 640×360 JPEG
- **THEN** the returned image is 640×360

#### Scenario: Face detection unavailable
- **WHEN** face blurring is on and face detection fails
- **THEN** the response is 502 `{"error": "camera unavailable"}` and no image is returned
