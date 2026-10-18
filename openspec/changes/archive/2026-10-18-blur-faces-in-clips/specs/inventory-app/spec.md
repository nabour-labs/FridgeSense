## ADDED Requirements

### Requirement: Clip picker plays face-blurred clips
The Reference images clip picker SHALL offer only the clips that `GET /api/events` returns as `clip` links, and SHALL play no other video. While face blurring is on, those links are face-blurred clips (see `clip-face-blur`). A frame grabbed from a clip SHALL still be sent to `POST /api/camera/frame`, and only the image that route returns SHALL be used.

#### Scenario: Only listed clips offered
- **WHEN** `GET /api/events` returns three recent events, two with a `clip` link and one with `clip: null`
- **THEN** the picker offers exactly the two clips, and its video sources are those two links

#### Scenario: Clip being blurred not offered
- **WHEN** the only recent event has `clip: null` because its clip is still being blurred
- **THEN** the picker shows "No door openings with a clip in the last 7 days."

#### Scenario: Frame still blurred by the server
- **WHEN** the owner picks a frame from a clip
- **THEN** `POST /api/camera/frame` is requested once with that frame, and the reference form shows the image it returns
