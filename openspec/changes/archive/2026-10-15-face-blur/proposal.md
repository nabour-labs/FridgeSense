# Proposal

## Why

The fridge camera sees whoever opens the door, so every still saved to S3, shown in the app or sent to Nova can show a person's face. Faces add nothing to the inventory. Keeping them out of everything we store and analyze answers Ring's privacy questionnaire, and it lets us show real stills in the demo video without exposing anyone in the household.

## What Changes

- Each still downloaded from Ring goes through face detection (Rekognition `DetectFaces`) **before** it is stored in S3. Every face found is blurred beyond recognition: the box is enlarged, pixelated, then given a strong Gaussian blur. Only the blurred image is stored.
- If no face is found, the still is stored exactly as downloaded.
- **Fail closed:** if face detection fails for a still, that still is dropped and counts as not downloaded. The existing rule (fewer than 2 stills → `no_media`, no analysis) applies, and an unblurred still is never stored.
- The door-open check and the Nova analysis read only the blurred stills. Nova never receives an unblurred image.
- Each detection call logs its cost (`face_detect_cost`), like the Nova cost log.
- The pipeline Lambda gets one new permission, `rekognition:DetectFaces`. It cannot be limited to specific resources, so it is granted on `*`.

Hackathon tracks: **Ring** (privacy by default for an indoor camera, which Ring's questionnaire asks about) and **AWS Builder** (Rekognition added to the Step Functions pipeline).

### Out of scope

- Recordings kept in the user's own Ring account. FridgeSense cannot change them.
- Blurring the demo video itself (screen recordings and phone footage). That is done by hand in a video editor.
- A fixed privacy mask over the area where heads usually appear. We'll reconsider once real stills show the camera angle.
- Blurring video clips. The MVP does not download clips.
- Going back over stills already in S3. They expire within 7 days under the existing lifecycle rule.
- Whole-body or person detection. Only faces are blurred.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `door-event-detection`: the "Stills across the opening" requirement now stores blurred stills. A new requirement says faces are blurred before a still is stored or analyzed, with fail-closed handling and a cost log.

## Impact

- **Code:** `backend/src/fridgesense/door_events.py` (`download_stills`, `fetch_stills`), a new face-blur module under `backend/src/fridgesense/`, and `handlers/pipeline.py` (builds the Rekognition client).
- **Infra:** `infra/lib/door-pipeline.ts` adds a `rekognition:DetectFaces` IAM statement and an optional `FACE_DETECT_PRICE` env var.
- **Dependencies:** none new. boto3 and Pillow are already used.
- **Cost:** about $0.001 per still, so roughly $0.004 per motion event. At 20–40 openings a day that's about $0.10–0.20 a day.
- **Latency:** about 4 extra Rekognition calls in the `fetch_stills` task, each well under 1 s.
- **Tests:** new unit tests that stub Rekognition with botocore Stubber; updates to the stills, fetch-stills and end-to-end pipeline tests; a CDK assertion for the IAM statement.
