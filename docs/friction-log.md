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

### 2026-10-17 · Ring Partner API · Live session "connects" for an unplugged camera but sends no video

- **Task:** take setup snapshots from a frame of the WHEP live view, and play the Livestream dialog.
- **Steps:** with the Indoor Cam's power cable unplugged, `GET /v1/devices/{id}?include=status,...` through our `GET /api/camera`, then `POST /v1/devices/{id}/media/streaming/whep/sessions` with a recvonly video+audio offer from Chrome, `setRemoteDescription` with the answer, and `getStats()` every 3 s for 42 s.
- **Expected:** the device shown offline, or the session refused with an error.
- **Actual:** the device status said `"online": true`. Ring answered the session with a normal SDP (`H264/90000 profile-level-id=64001f`, `OPUS/48000/2`, host candidates). ICE and DTLS reached `connected` in about 0.2 s and the browser fired the video track, but no RTP ever arrived: 26 transport packets in 24 s, no `inbound-rtp` stats, `framesDecoded` never above 0. The connection went to `disconnected` after about 27 s and `failed` after about 39 s. The app showed a black picture with a countdown.
- **Severity:** Medium
- **Workaround:** treat "no decoded video frame within 15 s of the answer" as "camera not sending video" and tell the user to check it's plugged in.
- **Suggestion:** refuse the WHEP session (for example 503 with a device-offline code) when the camera can't stream, and update the device's `online` status sooner.

### 2026-10-17 · Ring Partner API · No way to get a still of the camera "now"

- **Task:** take a current picture of the fridge for the setup screens (door references, fridge area).
- **Steps:** `POST /v1/devices/{id}/media/image/download` with `{"type": "at_timestamp", "timestamp": <now − 3 s>, "image_options": {"format": "jpeg"}}`, retried once after 2 s, from the deployed API whenever the owner tapped **Add**.
- **Expected:** a still of what the camera sees now. The docs describe the image as the nearest frame within ±10 s, which reads like it works at any time.
- **Actual:** every request with nobody moving in front of the camera got `416` and was logged as `{"event": "still_missing", "status": 416}` (four times between 13:15 and 13:18 UTC). The Indoor Cam only records on motion, so there is no frame near "now" unless something is moving, and the app showed "No recent footage" every time.
- **Severity:** Medium
- **Workaround:** fall back to a still at the middle of the newest motion event from `GET /v1/history/devices/{id}/events?event_types=motion`, and take setup snapshots from a frame of a short WHEP live view instead, with faces blurred on the backend.
- **Suggestion:** offer a "snapshot now" endpoint (the device lists a `snapshot` capability), or say in the image download docs that `at_timestamp` only finds frames inside recorded events.

### 2026-10-17 · Ring Partner API · Clip download answers 303 even when there is no clip

- **Task:** run the door check on frames from the motion event's clip instead of 30 separate stills.
- **Steps:** `GET /v1/history/devices/{id}/events?event_types=motion` (latest finished event, 20 s, about 15 h old), then `POST /v1/devices/{id}/media/video/download` with `{"timestamp": 1792181318101, "duration": 20026}`, then `GET` on the `Location` link. Read-only, once.
- **Expected:** a 303 to an MP4 for the event's recording, or an error on the POST if there is none. Our notes list the body as `{timestamp, duration}` without units.
- **Actual:** the POST answered `303` with `content-length: 0`. The link then answered `416 application/json`: `{"code":"MEDIA_NOT_FOUND","detail":"No media found in time range 1792181318101-1792181338127"}`. The range in the message shows `duration` is in milliseconds. The motion event is in history, but no clip is available for it.
- **Severity:** Medium
- **Workaround:** treat 416/425 from the link like the POST's (retry, then fall back to stills), and log `clip_unavailable` with the reason.
- **Suggestion:** document the units of `duration`, return `MEDIA_NOT_FOUND` from the POST rather than after the redirect, and say when a history event has no recording (for example a `has_recording` flag).

### 2026-10-16 · Ring Partner API · Device capabilities and configurations don't match the docs

- **Task:** show the camera's image enhancements (night vision, HDR) on the Config Camera tab.
- **Steps:** `GET /v1/devices/{id}?include=status,capabilities,configurations,location` for the Indoor Cam (read-only, once), compared with the Capabilities, Configurations and Status sections of the Partner API docs.
- **Expected:** `device-capabilities.image_enhancements.configurations` lists the on/off settings the device supports, each with a matching key in `device-configurations.image_enhancements`, as in the docs example (`color_night_vision`, `hdr`, `ir_led_night_vision`, `privacy_zones`).
- **Actual:** capabilities listed `["ir_led_night_vision", "privacy_zones", "snapshot"]`. `snapshot` is not documented and has no configuration key. Configurations still returned `color_night_vision`, `hdr` and `auto_zoom_track` (all `"off"`), which the camera does not list as supported. The camera's status also carried undocumented `reported_at`, `state` and `audio.snooze` fields (the docs describe snooze for chimes only), and the location resource id was `ava1.ring.location.<id>`, not `ava1.ring.device.location.<id>` as in the docs. The single-device route does honor `include` (the docs show it on the list route only).
- **Severity:** Low
- **Workaround:** show an enhancement only when it is in capabilities and configurations gives it an `"on"`/`"off"` value; follow relationship ids rather than assuming their format.
- **Suggestion:** document every capability value (what `snapshot` means), say whether configurations can hold unsupported settings, document `reported_at` and `state` on `device-status`, and show `include` on `GET /v1/devices/{id}`.

### 2026-10-16 · Ring Partner API · Doc pages from search results return 404

- **Task:** read the device status and device offline webhook docs.
- **Steps:** opened `https://developer.amazon.com/docs/ring/status.html` and `https://developer.amazon.com/docs/ring/device-offline.html`, both returned by a web search for the Partner API status and webhook docs.
- **Expected:** the Status and Device Offline pages.
- **Actual:** "404 Page not found" on both. The content now lives as sections of the single page `https://developer.amazon.com/docs/ring/api-documentation.html`, with no redirect from the old URLs.
- **Severity:** Low
- **Workaround:** searched the single API documentation page for the sections.
- **Suggestion:** redirect the old per-topic URLs to their anchors on the combined page.

### 2026-10-15 · Bedrock Nova · Nova 2 Lite caches a prefix under the documented 1K-token minimum

- **Task:** check that the Ask assistant's system-block `cachePoint` caches before shipping it.
- **Steps:** `set -a; source .env; set +a; cd backend && uv run python scripts/measure_prompt_cache.py --yes`. The script sent the same Converse request (2 tool specs, the system prompt and a cachePoint, then 3 messages) twice to `us.amazon.nova-2-lite-v1:0`.
- **Expected:** per the caching guide ("1K" minimum per checkpoint for Nova), no caching until the prefix reaches about 1,000 tokens.
- **Actual:** call 1 reported `cacheWriteInputTokens = 766` and call 2 `cacheReadInputTokens = 766`. Also, because cache writes are $0 for Nova 2 Lite and aren't counted in `inputTokens`, the call that writes the cache is cheaper than the call that reads it ($0.000156 against $0.000219). Not wrong, but surprising when reading cost logs.
- **Severity:** Low
- **Workaround:** none needed. We log cache reads and writes separately and price them from settings.
- **Suggestion:** give each Nova model's exact minimum in the caching guide, and say plainly that cache-write tokens are free and left out of `inputTokens`.

### 2026-10-15 · Bedrock Nova · Converse `cachePoint` after an image or toolResult block is rejected for Nova 2 Lite

- **Task:** measure prompt caching on the app's real request shapes before turning it on: the door-opening analysis (cache point after the reference images) and the assistant's tool loop (cache point after the tool results).
- **Steps:** `set -a; source .env; set +a; cd backend && uv run python scripts/measure_prompt_cache.py --yes`, which sends Converse requests to `us.amazon.nova-2-lite-v1:0` in us-east-1. The content is `[..., {"image": ...}, {"cachePoint": {"type": "default"}}, ...]` for analysis and `[{"toolResult": ...}, {"cachePoint": {"type": "default"}}]` for the assistant. Both pass botocore's offline parameter check.
- **Expected:** a cache write on the first call and a cache read on the second, as in the caching guide's Converse example, which puts a `cachePoint` right after an `image` block.
- **Actual:** every call failed with `ValidationException: ... Malformed input request: #/messages/0/content/4: extraneous key [cachePoint] is not permitted, please reformat your input and try again.` Index 4 is the image *before* the cache point. The assistant call failed the same way at `#/messages/2/content/0`, the `toolResult`. So Converse seems to fold the cache point into the preceding block, and Nova rejects it on image and toolResult blocks. Nothing in the guide or the API model says so, and botocore validation can't catch it.
- **Severity:** Medium
- **Workaround:** keep analysis caching off. Cache only the assistant's `system` block. Untested: cache points after a `text` block.
- **Suggestion:** list in the Nova rows which content block types a `cachePoint` may follow, fix the Converse example (it shows the cache point after an image), and have Converse return a clear error such as "cachePoint must follow a text block for this model".

### 2026-10-15 · Bedrock Nova · Prompt caching docs don't say whether image blocks can be cached

- **Task:** plan prompt caching for the door-opening analysis, whose stable prefix is mostly the owner's reference images (up to 6 JPEGs) and whose stills change every request.
- **Steps:** read https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html and looked for Nova 2 Lite's limits and cache pricing.
- **Expected:** a clear answer on whether a `cachePoint` after `image` blocks caches them for Nova, and Nova cache read/write prices.
- **Actual:** the Nova rows say only "Prompt caching is primarily for text prompts" with a 20K-token cap, while the generic Converse example puts a `cachePoint` right after an `image` block. Nova accepts checkpoints in `system` and `messages` but not `tools` (Claude accepts all three), and passing `ttl` to a 5-minute-only model can raise `ValidationException`. The Nova cache prices didn't come through when the pricing page was fetched as text.
- **Severity:** Low
- **Workaround:** a short measured test (send the same request twice, read `cacheWriteInputTokens` and `cacheReadInputTokens`) before relying on image caching.
- **Suggestion:** say plainly whether image and document blocks are cacheable for each Nova model, and put the cache read/write prices for each model in the caching guide.

### 2026-10-15 · MCP Python SDK · The MCP client logs full server URLs, secrets in the path included

- **Task:** live check of the Ask assistant: Nova calls our MCP server at `/mcp/<mcp_key>` through `mcp.Client(url)` from the API Lambda.
- **Steps:** asked three questions on the deployed app, then searched the API Lambda's logs: `aws logs filter-log-events --log-group-name /fridgesense/api --filter-pattern '"/mcp/"'`.
- **Expected:** no URLs in our logs; our own `ask_agent` events deliberately leave the URL out.
- **Actual:** 12 lines like `HTTP Request: POST https://<api>/mcp/<mcp_key> "HTTP/1.1 200 OK"`, from the `httpx2` logger the SDK's Streamable HTTP client uses, at INFO, which Lambda's root level lets through. On the server side, Mangum's `mangum.http` logger also wrote `POST /mcp/<mcp_key> 200` to the MCP Lambda's logs. A unit test on our own log events didn't catch either.
- **Severity:** Medium
- **Workaround:** set the `httpx`, `httpx2` and `mangum.http` loggers to WARNING, with tests that fail if the key appears in any log record. Rotate the key once the fix is deployed.
- **Suggestion:** have the SDK's HTTP transport log at DEBUG, or redact the path, and document that URL-embedded tokens end up in logs at INFO.

### 2026-10-15 · Strands Agents / MCP Python SDK · Strands can't share a project with an MCP server on `mcp` 2.3

- **Task:** build the Ask screen's assistant (Nova answering through our own MCP server) as a Strands agent in the backend, which already runs the MCP server on `mcp>=2.3,<3`.
- **Steps:** read the `strands-agents` metadata on PyPI (`https://pypi.org/pypi/strands-agents/json`), then resolved both together with `uv pip compile` on `mcp>=2.3,<3` + `strands-agents>=1.61`, and again with `strands-agents` unpinned.
- **Expected:** the latest Strands works with the latest MCP SDK.
- **Actual:** `strands-agents` 1.61.0 requires `mcp<2.2,>=1.23.0`. Pinned: "Because strands-agents>=1.61.0 depends on mcp>=1.23.0,<2.2 and you require mcp>=2.3, we can conclude that your requirements and strands-agents>=1.61.0 are incompatible." Unpinned, the resolver succeeds silently with `strands-agents==0.0.1`, a placeholder release, which is easy to miss.
- **Severity:** Medium
- **Workaround:** no Strands. A short Bedrock Converse tool-use loop uses the MCP SDK's own `mcp.Client` (Streamable HTTP) to call the tools. The other option was Strands in its own Lambda and project pinned to `mcp<2.2`.
- **Suggestion:** support `mcp` 2.x in Strands, or document the supported `mcp` range. Yank or mark the 0.0.1 placeholder so unpinned installs fail loudly.

### 2026-10-15 · AWS CDK / API Gateway · HTTP API route throttling needs the L1 stage, and its keys are not converted

- **Task:** throttle the HTTP API: a default limit for every route, and a lower limit on `POST /api/session` and `POST /ring/link`.
- **Steps:** looked for throttle props on `HttpApi` and its default stage; then set `defaultRouteSettings` and `routeSettings` on `api.defaultStage.node.defaultChild as CfnStage`, writing both in camelCase (`{ throttlingRateLimit: 1, throttlingBurstLimit: 3 }`), and asserted the template in a Vitest CDK test.
- **Expected:** a per-route throttle option on the L2 construct, and the same camelCase-to-PascalCase conversion for `routeSettings` that `defaultRouteSettings` gets.
- **Actual:** the L2 `HttpApi` default stage takes only a stage-wide `throttle`; per-route limits need the L1 `CfnStage`. `defaultRouteSettings` came out as `ThrottlingRateLimit`, but `routeSettings` (typed `any`, a map keyed by route key) went into the template unchanged as `throttlingRateLimit`/`throttlingBurstLimit`, which API Gateway would not recognize. Separately, API Gateway rejects route settings for a route key that doesn't exist yet, and CloudFormation doesn't infer the stage → route dependency from the route key string.
- **Severity:** Low
- **Workaround:** write the `routeSettings` values in PascalCase, `stage.node.addDependency(route)` for each throttled route, and assert both in a template test.
- **Suggestion:** add per-route throttling to the L2 HTTP API stage (for example `routeThrottle: { route, rateLimit, burstLimit }`), or type `CfnStage.routeSettings` as `Record<string, RouteSettingsProperty>` so the keys are converted.

### 2026-10-15 · AWS SDK (botocore) · `retries={"max_attempts": 1}` still makes two HTTP attempts

- **Task:** limit the Bedrock Converse client in the pipeline Lambda to a single HTTP attempt, so that Step Functions owns retries and two Nova calls fit inside the 90 s task timeout.
- **Steps:** configured `boto3.client("bedrock-runtime", config=Config(retries={"max_attempts": 1}, read_timeout=60))`, then asserted the resolved config in a test: `pipeline.bedrock_client().meta.config.retries["total_max_attempts"]`.
- **Expected:** 1 attempt in total.
- **Actual:** `assert 2 == 1`. In the client config, `max_attempts` counts retries, not attempts, so `max_attempts: 1` is one retry and two attempts in total. With `read_timeout=60` and our own second Nova request, one analyze call could take about 240 s and be killed at the Lambda's 90 s timeout.
- **Severity:** Medium
- **Workaround:** `Config(retries={"total_max_attempts": 1, "mode": "standard"}, connect_timeout=5, read_timeout=30)`, plus mapping botocore `ReadTimeoutError` and `ConnectTimeoutError` to our retryable error so the workflow retries them.
- **Suggestion:** give the two keys clearly different names in the retry docs and examples, or warn when `max_attempts` is set without a mode.

### 2026-10-15 · Ring Partner API · Account linking page asks for a fourth URL the docs don't mention

- **Task:** configure the Private app's account linking in the Ring developer console.
- **Steps:** opened the app's **Account linking** page in the developer console, after planning from the docs that a private app needs three public HTTPS URLs (Account Link, Token Exchange, Webhook).
- **Expected:** three URL fields.
- **Actual:** four fields: Account Link URL, **App Homepage URL** ("The URL where users can manage their connection to your service."), Token Exchange URL and Webhook URL. The docs we had read didn't say what the homepage URL is used for or whether it's required.
- **Severity:** Low
- **Workaround:** set App Homepage URL to the PWA (`SiteUrl` from the stack outputs).
- **Suggestion:** list all four fields in the account-linking docs, with where Ring shows the homepage URL to the user.

### 2026-10-14 · AWS CDK · Local bundling output picks up ANSI colors

- **Task:** build the Python Lambda asset in CDK local bundling by capturing `uv export` stdout into a requirements file, then `uv pip install --requirements`.
- **Steps:** `npx cdk synth -q` with `tryBundle` running `execFileSync("uv", ["export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes"])` and writing its stdout to a file.
- **Expected:** the same plain text `uv export` prints in a normal terminal.
- **Actual:** under `cdk synth` the captured output started with color codes (`\033[32m# This file was autogenerated…`), and the install failed: `error: Unexpected '', expected '-c', '-e', '-r' or the start of a requirement at …requirements-asset….txt:1:1`. The same call from plain Node printed no colors.
- **Severity:** Low
- **Workaround:** have uv write the file itself (`uv export … --quiet --output-file <path>`) instead of capturing stdout.
- **Suggestion:** document which environment variables (for example color settings) CDK passes to local bundling, or clear them for `tryBundle` subprocesses.

### 2026-10-14 · Alexa+ · MCP Toolkit setup looks gated for hackathon entrants

- **Task:** connect the FridgeSense MCP server to Alexa+ for the Alexa+ track.
- **Steps:** read the Alexa+ MCP Toolkit overview, quickstart and "Set up your development environment" pages under `developer.amazon.com/docs/alexaplus/add-ons/`.
- **Expected:** a self-serve path: install the `alexa-ai` CLI, sign in, register an MCP server URL, test in the simulator.
- **Actual:** setup refers to "the AWS account that you provided to the Alexa Solutions Architect", an IAM user that assumes an Amazon-provided role, and a private CodeArtifact registry. It isn't clear whether hackathon entrants get that access. The hackathon rules don't mention it either.
- **Severity:** Medium
- **Workaround:** none yet. We build to the rules (MCP 2025-11-25 over Streamable HTTP), test with MCP Inspector, and keep a simulated Alexa+ experience (allowed by the rules) as the fallback.
- **Suggestion:** say on the hackathon resources page whether entrants can use the Alexa+ MCP Toolkit, and how to request access.

### 2026-10-14 · MCP Python SDK · v2 breaks v1 code and needs care on Lambda

- **Task:** serve a stateless Streamable HTTP MCP server from AWS Lambda.
- **Steps:** installed `mcp` 2.3.0, followed v1-era examples (`FastMCP`), wrapped the Starlette app with Mangum, called it through an API Gateway event.
- **Expected:** v1 examples work; one ASGI app can serve many Lambda invocations.
- **Actual:** `mcp.server.fastmcp` now raises an error pointing to the migration guide (renamed to `MCPServer`). Reusing one Mangum-wrapped app fails on the second warm call with `LifespanFailure: ... run() can only be called once per instance`. The default DNS-rebinding protection answers `421 Invalid Host header` for the execute-api host.
- **Severity:** Medium
- **Workaround:** build a fresh app per invocation (`Mangum(build_app(), lifespan="on")`) and pass `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.
- **Suggestion:** an official serverless/Lambda example for stateless Streamable HTTP, and a session manager that can run more than once.

### 2026-10-14 · Amazon Bedrock · Nova 2 Lite has no in-region on-demand in us-east-1

- **Task:** call Nova 2 Lite with the Converse API from a us-east-1 Lambda.
- **Steps:** read the Nova 2 Lite model card.
- **Expected:** `amazon.nova-2-lite-v1:0` works on-demand in us-east-1, as the model card's own code sample shows.
- **Actual:** the availability table marks in-region as unsupported in us-east-1; only the `us.` (geo) and `global.` inference profiles work. The `us.` profile can route to us-east-2 and us-west-2 and costs about 10% more than `global.`. IAM then needs the profile ARN plus the foundation-model ARN in each destination region.
- **Severity:** Low
- **Workaround:** use `us.amazon.nova-2-lite-v1:0` and grant `bedrock:InvokeModel` on the profile and the three regional model ARNs.
- **Suggestion:** use the profile ID in the model card sample and say which regions a geo profile can route to on the same page.

### 2026-10-14 · Amazon Bedrock · Structured outputs not available for Nova

- **Task:** get a guaranteed JSON answer (items added and removed) from Nova.
- **Steps:** looked at Converse `outputConfig` structured outputs.
- **Expected:** JSON-schema structured output, as on other Bedrock models.
- **Actual:** both Nova 2 Lite and Nova Lite list structured outputs (and `strict`) as not supported.
- **Severity:** Low
- **Workaround:** a forced tool (`toolChoice: {"tool": {"name": "record_fridge_changes"}}`) at temperature 0, then Pydantic validation and one retry.
- **Suggestion:** support `outputConfig` JSON schemas on Nova models.

### 2026-10-14 · Ring Partner API · Token Exchange request format undocumented

- **Task:** implement the Token Exchange URL for one-way account linking.
- **Steps:** read the authentication section of the API documentation and the `AmazonAppDev/ring-api-helloworld` sample.
- **Expected:** the exact request Ring sends to the Token Exchange URL (content type and field names) and the response it expects.
- **Actual:** the docs only show sequence-diagram labels ("POST authorization code to Partner Token Exchange URL", "exchange within 60 seconds", "returns 200"). The sample doesn't implement account linking. The sample's webhook check is a plain bearer token, not the documented `X-Signature` HMAC, and its schema still lists `person_detected`.
- **Severity:** Medium
- **Workaround:** accept `code` from JSON, a form or the query string, and log only the field names so the first real link shows the format.
- **Suggestion:** document the Token Exchange request and response with an example, and update the sample to verify `X-Signature` over the raw body.

### 2026-10-14 · AWS Lambda + uv · Pillow 12 has no manylinux2014 wheels

- **Task:** bundle Pillow for a Python 3.13 arm64 Lambda with `uv pip install --python-platform aarch64-manylinux2014 --only-binary :all:` (no Docker).
- **Steps:** `cdk synth` with local uv bundling.
- **Expected:** arm64 wheels for every dependency.
- **Actual:** `Because pillow==12.3.0 has no usable wheels ... your requirements are unsatisfiable.` Pillow 12 ships only `manylinux_2_28` wheels.
- **Severity:** Low
- **Workaround:** target `aarch64-manylinux_2_28`; the python3.13 runtime runs on Amazon Linux 2023 (glibc 2.34).
- **Suggestion:** state the runtime's glibc and the matching manylinux tag on the Lambda Python runtime page.

### 2026-10-14 · AWS CDK · `TableV2` creates a global table

- **Task:** a single-region on-demand DynamoDB table in CDK.
- **Steps:** used `TableV2` (the newer construct) and asserted `AWS::DynamoDB::Table` in tests.
- **Expected:** a plain table.
- **Actual:** `TableV2` always synthesizes `AWS::DynamoDB::GlobalTable`, even with one region.
- **Severity:** Low
- **Workaround:** use the classic `Table` construct.
- **Suggestion:** mention in the `TableV2` docs that it is a global table resource even for one region.

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
