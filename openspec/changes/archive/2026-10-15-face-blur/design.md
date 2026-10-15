# Design

## Context

See proposal.md for the motivation.

Today `door_events.download_stills` downloads each still from Ring and calls `s3.put_object` right away. `fetch_stills` then runs the brightness door check on the bytes it returned. Later, `inventory.analyze_task` reads the stills back from S3 by `still_keys` and sends them to Nova. Since analysis reads from S3, one hook placed before `put_object` covers storage, the door check and Nova.

`fetch_stills` runs in the pipeline Lambda (512 MB, 90 s timeout, zip package, ARM64). boto3 and Pillow are already bundled, and Pillow already decodes stills for the door check. Retries are handled by the state machine, but only for the `analyze` step. `fetch_stills` has no state-machine retry for Rekognition errors.

## Goals / Non-Goals

**Goals:**
- One small, pure function that blurs the given face boxes in a JPEG. It can be unit-tested without AWS.
- A thin detector wrapper around Rekognition that the pipeline handler injects, so tests can swap in a botocore Stubber.
- Fail closed: no code path stores an unblurred still.

**Non-Goals:**
- Tuning blur parameters per camera, or exposing them as config. They are constants.
- Retrying Rekognition beyond boto's own single retry. A dropped still is acceptable because the opening usually still has ≥ 2 other stills.
- Any front-end change. The app already shows whatever is in S3.

## Decisions

### Rekognition `DetectFaces`, not a local model
- **Choice:** call `rekognition.detect_faces(Image={"Bytes": jpeg}, Attributes=["DEFAULT"])` from the existing Lambda.
- **Why:** no new dependency and no container image, and it's a managed AWS service that the AWS Builder judges will see. It handles profile and partial faces reasonably. The Bytes payload limit is 5 MB, and a 1080p JPEG is far below that.
- **Alternatives:**
  - OpenCV YuNet or MediaPipe in a container-image Lambda. Free per call, but adds a container build and image size the MVP plan cuts.
  - Asking Nova for face boxes. Unreliable, and Nova would already have seen the unblurred image.

### Inline bytes, called before storage
- **Choice:** detection gets the downloaded bytes directly, not an `S3Object`.
- **Why:** the unblurred image never touches S3, even briefly. This is spelled out as a spec scenario.

### Blur every face returned
- **Choice:** blur every face Rekognition returns, whatever its confidence.
- **Why:** `DetectFaces` has no minimum-confidence parameter, and it already drops very weak detections. A confidence cutoff could only *remove* blurs. Blurring all of them is the most conservative choice and meets the "bias to over-blurring" goal with no extra setting.
- **Alternative:** a configurable `FACE_MIN_CONFIDENCE` of 50. Rejected because it would only let faces through.

### Blur method: enlarge, pixelate, then Gaussian blur
- **Steps:**
  1. Grow each box by 30% about its centre. The width and height become 1.3×, which covers hair, ears and the box's loose edges.
  2. Clip the box to the image, then convert to pixels.
  3. Crop the region and shrink it to 8 px on its longer side (BOX averaging), then scale it back up (NEAREST). This removes the identifying detail.
  4. Apply `GaussianBlur(radius = max(4, longer_side_px / 6))` to hide the block edges.
  5. Paste the region back and re-encode as JPEG at quality 95.
- **Why both pixelate and blur:** a Gaussian blur on its own can be partly reversed, and pixelation alone looks harsh on camera. Doing both throws the information away and still looks clean.
- **Why quality 95:** it keeps re-encoding loss outside the boxes within the spec's ≤ 3 mean-absolute-difference limit.
- **No faces → no re-encode:** the original bytes are stored as they are, so ordinary stills lose no quality and the spec can require byte-identical output.

### Where the code lives
- **`fridgesense/faces.py` (new):**
  - `enlarge_box(box, factor=1.3) -> box`, which also clips.
  - `blur_regions(jpeg: bytes, boxes) -> bytes`, a pure function.
  - `FaceBlurrer(client, price_usd)`, whose `blur(jpeg, context) -> bytes | None` calls Rekognition, logs `face_detect_cost` or `face_detect_failed`, and returns `None` on any failure.
    - It catches `botocore.exceptions.ClientError` and `BotoCoreError`.
    - The error code comes from `ClientError.response["Error"]["Code"]`. For `BotoCoreError` it falls back to the exception class name.
- **`download_stills` / `fetch_stills`:**
  - Take a `blurrer` argument.
  - After a successful download, call `blurrer.blur(data, {account_id, device_id, still: n})`.
  - On `None`, `continue` (the still is dropped). Otherwise `put_object` the result and append `(key, blurred)` to `saved`.
  - The door check then sees the blurred bytes for free.
- **`handlers/pipeline.py`:**
  - Builds `boto3.client("rekognition", config=Config(retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10))`.
  - Builds `FaceBlurrer(client, float(os.environ.get("FACE_DETECT_PRICE") or 0.001))`.
  - Passes the blurrer into `fetch_stills`.
- **CDK, `door-pipeline.ts`:**
  - Add `fn.addToRolePolicy(new PolicyStatement({ actions: ["rekognition:DetectFaces"], resources: ["*"] }))`.
  - Add `FACE_DETECT_PRICE: props.faceDetectPrice`, from `context("faceDetectPrice", "0.001")` in `fridgesense-stack.ts`, the same way Nova's price is set.
- **`FaceBlurrer` as an argument:** it's passed explicitly rather than given a default, so no caller can forget it and silently store unblurred stills.

### Cost log
- `face_detect_cost` mirrors `nova_cost`: `account_id`, `device_id`, `still`, `faces`, `usd`.
- The `usd` value is the configured price per image. `Decimal` is used only if DynamoDB ever stores it; this change only logs it.
- `README.md` gets a matching `aws logs tail … --filter-pattern '"face_detect_cost"'` line next to the Nova one.

## Risks / Trade-offs

- **[Missed face]** A face that's very close to the lens, motion-blurred or mostly hidden may not be detected and would then be stored unblurred.
  - Mitigation: the box is enlarged, every detection is blurred, and stills expire after 7 days.
  - A static head-region mask stays a possible follow-up once real stills show the camera angle.
- **[Blurring an item]** An item held up next to the face gets blurred too, which may cost an item detection.
  - Accepted. The 4 stills usually show the item inside the fridge in another frame.
- **[Rekognition outage]** Every still is dropped, so events become `no_media` and the inventory doesn't update during the outage.
  - Accepted (fail closed). It shows up as `face_detect_failed` warnings.
- **[Latency]** Up to 4 × ~0.3–1 s extra in `fetch_stills`, plus one boto retry each.
  - Still well within the 90 s Lambda timeout and the target of updating the inventory "within a minute".
- **[Cost]** Paid even for motion events that aren't door openings, because blurring happens before the door check.
  - Moving the door check first would mean holding unblurred bytes longer and branching storage. At ~$0.004 per motion event that isn't worth it for the MVP.
- **[JPEG generation loss]** Re-encoding blurred stills can shift pixels outside the boxes.
  - Quality 95 keeps the shift small. Stills with no faces aren't re-encoded at all.

## Migration Plan

1. Deploy with `cdk deploy`, after Jayson's OK. The IAM statement and the new Lambda code ship together, so there is no window where the code calls Rekognition without permission.
2. Open the fridge once and check the logs for `face_detect_cost` and that the stored stills show blurred faces.
3. Stills stored before the deploy are unblurred and expire within 7 days. To clear them sooner, run `aws s3 rm --recursive` on the stills prefix, after Jayson's OK.
4. **Rollback:** redeploy the previous commit. Nothing in the data shape changes, because door events and keys are the same.

## Test strategy

- **Unit, pure (`tests/test_faces.py`):**
  - `enlarge_box` math and clipping, including the spec's `(0.40, 0.20, 0.20, 0.30)` → `(0.37, 0.155, 0.26, 0.39)` case and the edge box `(0.90, -0.05, 0.15, 0.25)`.
  - `blur_regions` on a checkerboard JPEG:
    - luminance std dev inside the box < 10;
    - mean absolute difference outside the box ≤ 3;
    - two boxes;
    - an edge box with no exception.
- **Unit, detector (`tests/test_faces.py`):** `FaceBlurrer` with a botocore `Stubber` on a real `boto3.client("rekognition", region_name="us-east-1")`:
  - expected params `Image={"Bytes": <downloaded>}`;
  - responses with 0, 1 and 2 faces, and a face with `Confidence = 50.2`;
  - `add_client_error` for `ThrottlingException`, `InternalServerError`, `InvalidImageFormatException` and `ImageTooLargeException` → `None`;
  - `caplog` assertions on `face_detect_cost` (default price and 0.0008) and on `face_detect_failed`, with no cost line on failure.
- **Component (`tests/test_stills.py`, `tests/test_fetch_stills_task.py`):**
  - The existing respx-mocked Ring plus moto S3/DynamoDB, with a fake blurrer: a tiny object whose `blur` returns marked bytes, or `None` for chosen still numbers.
  - Asserts the stored S3 bodies equal the blurred bytes, the gaps when a still is dropped, `no_media` when all 4 are dropped, and the door check on blurred bytes.
  - Existing tests are updated to pass a "no faces" blurrer that returns its input, so their current assertions keep holding.
- **Integration (`tests/test_pipeline_e2e.py`):**
  - Run the handler path with a Stubber-backed Rekognition client that reports one face for still 1, and the existing stubbed Bedrock.
  - Assert the image bytes in the Converse request equal the stored blurred object and differ from the downloaded bytes.
- **Infra (`infra/test/pipeline.test.ts`):**
  - The pipeline Lambda role has exactly one `rekognition:*` action, `rekognition:DetectFaces`, on `*`.
  - The function env has `FACE_DETECT_PRICE`.
- **Fixtures:**
  - A `checkerboard_jpeg()` helper in `tests/conftest.py`, built in code with no binary file.
  - `tests/fixtures/rekognition/detect_faces_one.json` and `detect_faces_two.json`, canned `DetectFaces` responses with `FaceDetails[].BoundingBox` and `Confidence`.
- **Stubbed:** Rekognition (Stubber), Bedrock (existing stub), Ring (respx), S3/DynamoDB/Secrets Manager (moto). Nothing calls live services.

## Open Questions

- Should a face be blurred more strongly than the defaults (bigger enlargement, fewer pixel blocks)? This can be tuned after looking at real stills without changing the specs, because the spec thresholds are minimums.
