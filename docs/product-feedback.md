# Product feedback

Feedback on every tool, API and SDK FridgeSense uses, for the Devpost "product feedback" field. Each section covers how we used it, what worked, what needs work, onboarding, and whether we would build with it again. Details and exact errors are in the [friction log](friction-log.md); this file links to it rather than repeating it.

Built Oct 14–22, 2026 by one developer: a Python 3.13 backend (Lambda, Step Functions), a TypeScript CDK app and a React PWA, all test-first, with no live Ring or AWS calls in tests.

## Ring Partner API

**How we used it:** a Private app with one-way account linking (Account Link page, Token Exchange URL), tokens in Secrets Manager refreshed every 3 hours, `GET /v1/devices` with `include`, motion webhooks verified by `X-Signature`, event history to find each motion's start and end, clip download (`media/video/download`) for the door check, stills (`media/image/download`) for analysis, live video over WHEP (60 s sessions), and `device_online`/`device_offline` webhooks for the camera's uptime history.

**What worked**

- The building blocks fit a non-security use well. Webhook → history → clip → stills gave us everything we needed to turn a motion into a door opening with exact open and close times.
- The webhook contract is clear and safe to build on: HMAC over the raw body, `meta.request_id` for dedupe, documented retry behaviour for 5xx versus 4xx.
- Private apps need no certification, so we went from console to a linked camera on day 1.
- WHEP live video was the easiest feature to add: the backend only relays the SDP offer and answer, so the Ring token never reaches the browser.
- `AmazonAppDev/ring-api-helloworld` was a useful reference for tokens and the WHEP proxy.

**What needs work**

- **Token Exchange is undocumented.** The docs show only sequence-diagram labels, not the request Ring sends (content type, field names) or the response it expects, and the sample doesn't implement account linking. We had to accept every plausible format and log field names to find out.
- **Clip download fails late.** The POST answers `303` even when there is no recording; the error (`416 MEDIA_NOT_FOUND`) only comes from the redirect target. `duration` units (milliseconds) are not documented, and a history event doesn't say whether it has a recording.
- **Docs drift from the API.** Capabilities included an undocumented `snapshot`; configurations returned settings the camera doesn't support; `device-status` had undocumented fields; the location id format differed from the docs.
- **Watermark on all media** (since June 8, 2026) is only in the release notes, not on the media pages, with no size or position given. For AI use this matters: we had to check it stays out of the door zones and that Nova doesn't list it as an item.
- **Docs are hard to navigate:** search sent us to the `/zh/` page, old per-topic URLs return 404 with no redirect, and the account-linking page in the console has a fourth field (App Homepage URL) the docs don't mention.
- **No SDK.** Token refresh, signature checks and download retries are written by hand by every partner.

**Onboarding:** fast to a first API call (Developer Playground, Private app), slow to a working account link because of the Token Exchange gap.

**Would we build with it again?** Yes. The data is what makes the product possible, and the problems are documentation, not design. Top requests: document Token Exchange with an example, fail clip downloads on the POST, and ship a small Python/JS client.

Friction log: 7 Ring entries (Oct 14–17).

## Alexa+ (MCP Toolkit)

**How we used it:** FridgeSense exposes a read-only MCP server (spec 2025-11-25, Streamable HTTP) with six tools (`find_item`, `get_inventory`, `fridge_activity`, `last_opened`, `oldest_items`, `low_stock`), built to the track rules so Alexa+ can answer "do I have milk?".

> **TODO (Jayson):** update this section with the result of `alexa-ai configure` / `new mcp` / `deploy` before submitting. If it works, describe the setup and the simulator test; if not, keep the text below.

**What worked:** building to an open protocol meant the same server works today with MCP Inspector, Claude Desktop and our own Ask screen (Nova as the MCP client), so nothing was wasted while access was unclear.

**What needs work:** the MCP Toolkit setup refers to "the AWS account that you provided to the Alexa Solutions Architect", an Amazon-provided IAM role and a private CodeArtifact registry. Neither the docs nor the hackathon rules say whether entrants get that access or how to request it. We built a simulated Alexa+ experience (allowed by the rules) as a fallback.

**Onboarding:** blocked at the first step for us, on access rather than on anything technical.

**Would we build with it again?** Yes, if access is self-serve. Request: say on the hackathon resources page whether entrants can use the toolkit and how to get access.

## Amazon Bedrock: Nova 2 Lite

**How we used it:** two jobs through the Converse API. (1) Door-opening analysis: up to 4 face-blurred stills plus up to 6 reference images and custom instructions, answered through a forced tool (`record_fridge_changes`) at temperature 0, validated with Pydantic and retried once. (2) The Ask assistant: a Converse tool-use loop where Nova calls our MCP tools and answers in one or two sentences. Prompt caching on the assistant's system block. Token use and cost logged per call and stored per door event.

**What worked**

- **Cost.** About $0.0014 per door opening and well under $0.01 per question, which makes per-opening analysis viable for a household that opens the fridge 20–40 times a day.
- Image understanding is good enough for item types (milk, eggs, a soda can) from a ceiling-mounted camera, and reference images with notes clearly help with household-specific items.
- Converse tool use covers both jobs: a forced tool at temperature 0 plus Pydantic validation gives checked JSON for analysis, and the same API drives the agent loop.
- Converse returns `latencyMs` and cache token counts, which made cost and performance logging easy.
- Prompt caching worked on the system block, even below the documented minimum.

**What needs work**

- **No structured outputs** (`outputConfig` JSON schema) on Nova, unlike other Bedrock models. The forced-tool workaround works but is a workaround.
- **`cachePoint` after an image or `toolResult` block is rejected** with "extraneous key [cachePoint] is not permitted", although the caching guide's Converse example puts one after an image, and botocore's validation can't catch it. The guide doesn't say whether images are cacheable for Nova, gives "1K" as the minimum while 766 tokens cached, and doesn't say cache writes are free and excluded from `inputTokens`.
- **No in-region on-demand in us-east-1** for Nova 2 Lite, while the model card's own sample uses the in-region ID. The `us.` profile routes to three regions, which needs three model ARNs in IAM and matters for data residency.

**Onboarding:** easy to a first Converse call; the time went into caching experiments and the inference profile.

**Would we build with it again?** Yes. Price and multimodal quality are the reason the product works. Top requests: structured outputs for Nova, and caching docs that match what the API accepts.

Friction log: 5 Bedrock/Nova entries.

## MCP Python SDK (`mcp` 2.3)

**How we used it:** the server side (`MCPServer`, stateless Streamable HTTP) on Lambda behind API Gateway via Mangum, and the client side (`mcp.Client`) inside the Ask assistant, so Nova calls the same tools Alexa+ would.

**What worked:** one tool definition serves Alexa+, MCP Inspector, Claude Desktop and our own agent. Stateless Streamable HTTP suits Lambda: no sessions to store. Spec 2025-11-25 support was there in the current release.

**What needs work**

- v2 breaks v1 code (`FastMCP` → `MCPServer`), and almost every example online is v1.
- On Lambda, a reused app fails on the second warm call (`run() can only be called once per instance`), and DNS-rebinding protection answers `421 Invalid Host header` for the execute-api host. Both need workarounds found by trial.
- The client's HTTP transport logs full request URLs at INFO, so a key in the URL path ends up in CloudWatch.

**Onboarding:** medium. The SDK itself is clean; the missing piece is a serverless example.

**Would we build with it again?** Yes. Requests: an official Lambda example for stateless Streamable HTTP, a session manager that can run more than once, and transport logging at DEBUG.

## Strands Agents (evaluated, not used)

We planned the Ask assistant as a Strands agent. `strands-agents` 1.61 requires `mcp<2.2`, and our MCP server needs `mcp>=2.3`, so they can't share a project; unpinned, uv silently resolved `strands-agents==0.0.1`, a placeholder. We wrote a short Converse tool-use loop instead. We'd try Strands again once it supports `mcp` 2.x. Request: support `mcp` 2.x, document the supported range, and yank the 0.0.1 placeholder.

## AWS CDK (TypeScript)

**How we used it:** one stack for everything: HTTP API, Lambdas built locally with uv (no Docker), Step Functions, DynamoDB, two S3 buckets, CloudFront, Secrets Manager, EventBridge schedules, an alarm with SNS email and a budget. Every construct choice is checked by Vitest template assertions, and `cdk diff` before each deploy.

**What worked:** one `cdk deploy` from a laptop builds the PWA and the backend. L2 constructs and `grant*` methods kept IAM tight with little code. `Template.fromStack` assertions let us test infrastructure the same way as code. Local bundling with uv kept deploys fast without Docker.

**What needs work**

- `TableV2` always creates a `GlobalTable`, even in one region; the docs don't say so.
- No per-route throttling on the L2 HTTP API stage; on the L1 `CfnStage`, `routeSettings` is typed `any` and its keys aren't converted to PascalCase, so camelCase values silently do nothing. The stage → route dependency must be added by hand.
- Bundling can't be skipped from the CLI (`aws:cdk:bundling-stacks` is rejected as user context), and local bundling subprocesses inherit color settings that broke captured output.

**Onboarding:** easy for us (already familiar).

**Would we build with it again?** Yes, it's our default for AWS.

Friction log: 3 CDK entries plus 1 shared with API Gateway.

## Other AWS services

| Service | How we used it | What worked | What needs work |
| --- | --- | --- | --- |
| **AWS Lambda** (Python 3.13, arm64) | Webhook, API, pipeline steps, token refresh, MCP server | Zip packages built with uv, no containers; the webhook replies well inside Ring's 5 s by handing work to Step Functions | The runtime page doesn't state its glibc or matching manylinux tag; Pillow 12 needs `manylinux_2_28` |
| **AWS Step Functions** | One run per motion: wait for the recording, read history, door check, stills, Nova, save | Waits and per-error retries (`BedrockRetryable`) with no code; the visual run history is the best debugging tool we had | Nothing blocking |
| **Amazon API Gateway** (HTTP API) | Ring's three URLs, the PWA's API and the MCP endpoint | Cheap and simple; Lambda proxy integration just works | Per-route throttling only on the L1 stage (see CDK) |
| **Amazon DynamoDB** | One table: door events, inventory, analysis results, traces (TTL) | On-demand pricing is pennies; TTL handles expiry | Nothing blocking |
| **Amazon S3** | Face-blurred stills and debug traces, 7-day lifecycle rule; PWA hosting | Lifecycle rules make "auto-delete after 7 days" a one-liner | Nothing blocking |
| **Amazon CloudFront** | Serves the PWA and proxies `/api` to the HTTP API | One origin for app and API, so no CORS | Nothing blocking |
| **AWS Secrets Manager** | Ring client secret, HMAC key, tokens, passcodes, MCP key | Rotating a passcode or the MCP key is one CLI command | Nothing blocking |
| **Amazon Rekognition** (`DetectFaces`) | Blur every face before a still is stored or sent to Nova | One call per still, $0.001 each; a failed call drops the still rather than storing it unblurred | No `MinConfidence` to lean toward over-blurring; IAM can't be limited below `Resource: *` |
| **Amazon Polly** (neural, Joanna) | Reads Ask answers aloud | Natural voice, simple API, browser voice as a fallback | Nothing blocking |
| **Amazon EventBridge** | Token refresh every 3 h; MCP Lambda warm-up every 5 min | Simple schedule rules | Nothing blocking |
| **Amazon CloudWatch** | Structured JSON logs (`nova_cost`, `face_detect_cost`, `ask_agent`), alarm on failed runs | `aws logs tail --filter-pattern` is enough for cost tracking | Third-party loggers (httpx, Mangum) log URLs at INFO by default (see MCP SDK) |
| **Amazon SNS** and **AWS Budgets** | Email on failed door-event runs and at 80% of a $60/month budget | Easy guardrails when paying out of pocket | The SNS email must be confirmed by hand after the first deploy |
| **AWS SDK for Python** (boto3) | Every AWS call | Botocore Stubber and moto let us test without AWS | `retries={"max_attempts": 1}` means two attempts; the key naming is easy to get wrong |

**Would we build with them again?** Yes. The whole backend is serverless, costs a few dollars a month at one household's traffic, and every privacy rule (face blur, 7-day expiry, crop) maps onto a managed feature.

## Feature requests, by priority

1. **Ring:** document the Token Exchange request and response, with an example. *(High)*
2. **Alexa+:** self-serve MCP Toolkit access for hackathon entrants, or clear steps to request it. *(High)*
3. **Bedrock:** structured outputs (`outputConfig` JSON schema) for Nova models. *(Medium)*
4. **Ring:** return `MEDIA_NOT_FOUND` from the clip download POST, document `duration` units, and add a `has_recording` flag to history events. *(Medium)*
5. **Ring:** a small official Python/JS client (tokens, webhook signatures, media download). *(Medium)*
6. **Bedrock:** caching docs per Nova model: which blocks a `cachePoint` may follow, image support, exact minimums, cache pricing. *(Medium)*
7. **MCP Python SDK:** an official Lambda example for stateless Streamable HTTP, and a reusable session manager. *(Medium)*
8. **Strands:** support `mcp` 2.x. *(Medium)*
9. **Ring:** document the media watermark's size and position, or allow it off for machine analysis. *(Low)*
10. **Rekognition:** `MinConfidence` on `DetectFaces`. *(Low)*
11. **CDK:** per-route throttling on the HTTP API L2 stage, and a `--no-bundling` flag. *(Low)*
