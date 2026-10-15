# Friction log

This file records friction we hit with the services the hackathon covers: the Ring Partner API, Alexa+, AWS (Bedrock Nova, Rekognition, CDK, Step Functions, Lambda, S3, DynamoDB and the rest), MCP and Strands, and Fire TV. Add an entry as soon as the friction happens, while the details are fresh. The submission's friction log and product feedback are built from these entries.

**Severity:**
- **High:** blocks the task, with no workaround.
- **Medium:** costs real time or changes the design.
- **Low:** annoying but quick to work around.

Each entry uses this template. Put the newest entry first.

```markdown
### YYYY-MM-DD · <service> · <one-line title>

- **Task:** what we were trying to do
- **Steps:** what we did, in order (commands, endpoints, console pages)
- **Expected:** what we thought would happen
- **Actual:** what happened (exact error text when there is one)
- **Severity:** High / Medium / Low
- **Workaround:** how we got past it (or "none yet")
- **Suggestion:** what the service could change
```

## Entries

### 2026-10-14 · Ring Partner API · Mandatory watermark on downloaded media

- **Task:** analyze the fridge-camera stills with Nova and a brightness check on the door area.
- **Steps:** read the Ring Partner API release notes while looking up the media download docs.
- **Expected:** the stills come out as the camera captured them, like the image the Ring app shows.
- **Actual:** since June 8, 2026, all media from the Partner API has a watermark that can't be turned off: the Ring logo top-left, and the device ID, app name and timestamp top-right. Only the release notes mention it; the media endpoint pages don't. The notes say teams running AI/ML on media may need to retrain their models.
- **Severity:** Medium
- **Workaround:** none needed yet. We'll check that the watermark stays outside the door-check box (`0.25,0.1,0.5,0.8`) on the first real stills, and that Nova doesn't list it as an item.
- **Suggestion:** document the overlay's size and position on the media download pages, or add an option to leave it out of stills used only for machine analysis.

### 2026-10-14 · Ring Partner API · Docs hard to find; no SDK

- **Task:** find the reference pages for webhooks and media download.
- **Steps:** searched the web for the Ring developer API docs.
- **Expected:** one English API reference page and an SDK or client library.
- **Actual:** search sent us to the `/zh/` version of the API documentation page. The webhook, media and getting-started docs are on separate pages. There is no SDK, so token refresh, webhook signature checks and media download retries are all written by hand.
- **Severity:** Low
- **Workaround:** used the English pages under `developer.amazon.com/docs/ring/` and the `AmazonAppDev/ring-api-helloworld` sample.
- **Suggestion:** a single English API reference index, and a small official client for Python and JS covering tokens, webhook signatures and media download.

### 2026-10-14 · Amazon Rekognition · `DetectFaces` IAM can't be limited to specific resources

- **Task:** give the pipeline Lambda least-privilege access to detect faces in stills.
- **Steps:** added an IAM statement for `rekognition:DetectFaces` in CDK and tried to set a resource ARN.
- **Expected:** a resource ARN to limit the permission, as we did for Bedrock (inference profile and model ARNs).
- **Actual:** `DetectFaces` works on image bytes and has no resource type, so the statement must use `"Resource": "*"`.
- **Severity:** Low
- **Workaround:** granted only `rekognition:DetectFaces` on `*`, with a CDK test that it's the only Rekognition action.
- **Suggestion:** support condition keys (for example on the calling Lambda) so these actions can be narrowed.

### 2026-10-14 · Amazon Rekognition · `DetectFaces` has no minimum-confidence parameter

- **Task:** blur faces and lean toward over-blurring with a low confidence cutoff (about 50).
- **Steps:** looked for a `MinConfidence` parameter on `DetectFaces`, like the one on `DetectLabels`.
- **Expected:** a way to have it return weaker detections.
- **Actual:** there's no such parameter. The service applies its own threshold, so a client-side cutoff can only remove faces, never add them.
- **Severity:** Low
- **Workaround:** blur every face it returns, whatever its confidence.
- **Suggestion:** add `MinConfidence` to `DetectFaces` for privacy uses where false positives are cheap.

### 2026-10-14 · AWS CDK · Can't skip bundling from the CLI

- **Task:** run `cdk synth` without bundling the Python Lambda, as the unit tests do.
- **Steps:** `npx cdk synth -c 'aws:cdk:bundling-stacks=[]' --quiet`
- **Expected:** the same no-bundling synth that `new App({ context: { "aws:cdk:bundling-stacks": [] } })` gives in tests.
- **Actual:** `User-provided context cannot use keys prefixed with 'aws:', but aws:cdk:bundling-stacks was provided.`
- **Severity:** Low
- **Workaround:** ran a full `cdk synth` with local uv bundling.
- **Suggestion:** a documented `--no-bundling` flag, or allow this one `aws:` key from the CLI.
