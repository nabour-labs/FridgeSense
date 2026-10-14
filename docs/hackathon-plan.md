# FridgeSense — Hackathon Plan

Oct 14, 2026 · @Jayson

## Summary

**FridgeSense** uses a Ring Indoor Cam 2K to watch the fridge. Each time the door opens, the clip goes to S3 and Amazon Bedrock Nova lists what was put in or taken out. The app keeps a running inventory and open/close statistics (by hour, day, week, month).

- **Deadline:** Friday Oct 23, 12:00 pm PT. Today is Oct 14, so 9 days.
- **Entering:** Ring track and Alexa+ track; AWS Builder and Open Source mini challenges. Fire TV only if time allows.
- **Front ends:** a PWA (main app) and an MCP server ("Alexa, do I have milk?").
- **Later:** publishing to the Ring Appstore is undecided. The build keeps that option open (see below) but adds no work for it.

## Demo MVP scope (decided Oct 14)

One user (Jayson), one camera, one fridge. The goal is a sub-3-minute video that passes the Ring and Alexa+ fit checks and scores on the four criteria. **This section overrides the rest of the plan where they disagree;** everything cut below is a stretch goal for after the MVP works end to end.

**The video in one line:** put milk in the fridge → the inventory updates on the phone within a minute → "Alexa, do I have milk?" → "Yes, 1 milk, added 2 minutes ago."

| Area | Keep (minimal version) | Cut or defer |
| --- | --- | --- |
| Tracks | Ring, Alexa+, AWS Builder mini | Open Source mini (needs a second repo; only one mini prize anyway), Fire TV, Bee |
| Ring access | Private app, one-way account link, token exchange, tokens in Secrets Manager, scheduled refresh | Lifecycle webhooks (`app_integration_removed` etc.), subscription checks |
| Sign-in | Account Link page and PWA behind one passcode in Secrets Manager | Cognito |
| Webhook | Signature check, dedupe by `meta.request_id`, 200 fast, start the workflow | — |
| Workflow | Step Functions: wait → fetch event end → download 3–4 stills → brightness door check (Pillow) → Nova → save | Video clips, ffmpeg, container-image Lambda |
| Analysis | Nova Lite via Converse on stills, Pydantic-checked JSON, cost logged per opening | Reference images / item catalog, embeddings |
| Data | DynamoDB single table: door events, inventory items, analysis results. S3 stills, 7-day lifecycle | "Delete my data" UI (one user: a cleanup script is enough) |
| PWA | Inventory list, "added/removed" feed, confirm or fix low-confidence items, opens-per-day and by-hour charts. S3 + CloudFront | Item photos, week/month views, notifications |
| Alexa+ | Stateless MCP server on Lambda: `get_inventory`, `find_item`, `fridge_activity`, `last_opened` | Strands agent ("what can I cook?") — stretch; Alexa+'s own model can combine the tools |
| Deploy | `cdk deploy` from the Mac | CI deploys, CodePipeline |

**Build order** (each one OpenSpec change, test-first):

1. `ring-access` (Oct 14–15): CDK skeleton, account link + token exchange, token refresh, `GET /v1/devices`
2. `door-event-pipeline` (Oct 16–17): webhook → Step Functions → stills → door check → Nova → DynamoDB
3. `inventory-pwa` (Oct 18–19): the phone app
4. `fridge-mcp` (Oct 20): MCP server, tested with MCP Inspector, then Alexa+
5. Oct 21: tune camera angle and prompt on real openings; stretch goals only if 1–4 work
6. Oct 22: record the video, README setup steps, product feedback, friction log, submit (a day of buffer before the deadline)

## Hackathon rules that matter

Submissions close **Oct 23, 12:00 pm PT**; judging runs Nov 9–20 and winners are announced around Dec 3. Source: [official rules](https://amazonappdev2026.devpost.com/rules).

| Topic | Rule |
| --- | --- |
| Who can enter | Individuals, teams, and existing organizations (one Representative submits). Quebec residents and Quebec-based organizations are excluded |
| AWS credits | Ran out on Oct 7. All AWS usage is paid by us |
| Ring track requirement | Code must actually call Ring APIs at runtime; the demo must show a real Ring device or Ring's simulator |
| Repo | Public with an open-source license, **or** private and shared with testing@devpost.com and the listed Amazon GitHub reviewers. Must include setup and run instructions |
| Video | Under 3 minutes, public on YouTube or Vimeo, shows the project running on the real device. No copyrighted music |
| Product feedback | Required for each tool, API and SDK used: what worked, what needs work, onboarding, would you build again |
| Friction log | Optional, worth up to a 10% bonus |
| Judging | Pass/fail fit check, then four equal criteria: technical implementation, design, potential impact, quality of the idea |
| Prizes | Ring: $12k (1st), $8k (2nd). Alexa+: $25k / $15k / $4k plus AWS credits. AWS Builder and Open Source: $5k + $5k credits each |
| Prize limit | One track prize and one mini-challenge prize per project |

## Tracks

One project enters several tracks. Each track is checked pass/fail first, so every entry needs real use of that track's technology, shown in the same video.

| Track | Fit | What we build for it | Decision |
| --- | --- | --- | --- |
| Ring | Strong — the core idea; the rules list non-security use and event triggers as creative | Camera webhook → clip → analysis pipeline, PWA | Enter |
| Alexa+ | Strong | Self-hosted MCP server (spec 2025-11-25, Streamable HTTP): "do I have milk?", "what's expiring?", "what can I cook?" | Enter |
| AWS Builder (mini) | Strong | S3 + Bedrock Nova + a Strands agent behind the MCP server; documented in product feedback | Enter |
| Open Source (mini) | Good | A small, separate open-source Ring API client (token refresh, webhook signature check, clip download) | Enter |
| Fire TV | Weak to moderate | Kitchen dashboard in the Fire TV / Vega simulator | Only if everything else is done by Oct 20 |
| Bee | Poor — needs Bee wearable data | — | Skip |

## Hardware and accounts

The camera is ordered: **Ring Indoor Cam 2K** ($79.99, amazon.ca). The API caps clips and stills at 1080p, so the 2K was chosen for earlier delivery and better handling of the bright fridge light.

- [ ] Measure the cable route; if the included 6.5 ft (2 m) cable is short, buy the Ring 10 ft USB-A to USB-C cable ($21.99) or mount on top of the upper cabinets instead
- [ ] Set up the camera in the Ring app; turn on **Motion Recording**; check Smart Alerts and motion zones don't filter out the fridge
- [ ] Start the Ring subscription trial (\~30 days). It ends around Nov 14, during judging — pay for a month if judges might test live
- [ ] Join the hackathon on Devpost
- [ ] Register as a Ring developer at developer.amazon.com/ring/console and create a **Private** app (Cameras and Doorbells scope)
- [ ] Save the Client ID, Client Secret and webhook signing key immediately — they are shown only once
- [ ] Turn on Amazon Nova model access in Bedrock; set an AWS budget alarm at $20–30
- [ ] Create the GitHub repo (private, shared with the judges) and a separate public repo for the open-source Ring client

* Optional: Ring contact sensor for exact open/close times — probably needs a Ring Alarm base station; sensor scope is Early Access

## Architecture

&#91;embedded content: architecture · Ring camera to front ends\]

Ring sends a webhook for each motion event; the worker downloads the clip and stills, and only real door openings reach Nova. Every front end reads the same inventory store.

## Tech stack

Python for everything that touches Ring, Bedrock and the agent; TypeScript for the PWA and the CDK infrastructure code. Region: us-east-1.

| Layer | Pick | Why | Instead of |
| --- | --- | --- | --- |
| Infrastructure as code | AWS CDK (TypeScript) | Already familiar; one `cdk deploy` for everything | SAM, Terraform |
| Public endpoints (webhook, account link, token exchange) | API Gateway HTTP API → Python Lambdas | The three HTTPS URLs Ring requires, no server to run | A container service |
| Webhook handling | Lambda: check signature, skip repeats, start the workflow, reply 200 | Meets Ring's 5-second rule | Doing the work inside the webhook |
| Clip workflow | Step Functions: wait → read event end → download clip + stills → door check → Nova → save | Built-in waits and retries; a visual workflow for the demo and AWS Builder judges | An SQS delay loop |
| Frames + door check | Container-image Lambda with ffmpeg + Pillow | Brightness in the door area; ffmpeg doesn't fit a zip Lambda | OpenCV |
| Clip analysis | Bedrock Converse API with Nova Lite (Nova 2 Lite if available), output checked against Pydantic models | One call per opening; bad JSON rejected | An agent framework for this step |
| Database | DynamoDB, one table (inventory items, item catalog with reference photos, door events, analysis results) | Serverless, no VPC, pennies a day | Aurora/Postgres |
| File storage | S3, raw clips auto-deleted after \~7 days | Privacy by default; Nova reads clips from S3 | — |
| Secrets | Secrets Manager; a scheduled Lambda refreshes the Ring token every \~3 h | Access tokens last 4 h | Environment variables |
| Sign-in | Cognito user pool with its managed login page | Ring's required sign-in page and the PWA login | Writing our own auth |
| Agent | Strands Agents (Python) on Lambda; AgentCore Runtime as a stretch goal | Named by AWS Builder judges; shares tools with the MCP server | LangChain, Pydantic AI |
| MCP server (Alexa+) | Official Python MCP SDK, Streamable HTTP, stateless on Lambda | The track requires spec 2025-11-25 over Streamable HTTP | A Node MCP server |
| PWA | Vite + React + TypeScript, `vite-plugin-pwa`, Tailwind, Recharts | Fastest installable phone app; charts for open/close stats; camera/photo upload for reference images | Next.js, Flutter, React Native |
| PWA hosting | Amplify Hosting (or S3 + CloudFront) | Fewest steps from git push to a live link | — |
| Tests | pytest with recorded Ring webhooks and canned API responses | No live Ring calls in tests; reliable demo | — |
| Open-source piece | Small Python package: token refresh, webhook signature check, clip/still download with retries, MIT | Extracted from the webhook and workflow code | — |

**Avoid this week:** Aurora/Postgres (VPC and connection overhead), LangChain (too much framework for six tools), Flutter or React Native (app builds), self-hosted WebRTC recording (motion events already record).

**MCP tools:** `get_inventory`, `find_item`, `low_stock`, `oldest_items`, `fridge_activity(period)`, `last_opened`. The Strands agent combines them for open questions such as "what can I cook tonight?" and "was anything unusual today?".

**To check:**

- [ ] The installed MCP SDK version supports spec 2025-11-25
- [ ] How a judge reaches the MCP server through Alexa+. Fallback: demo with MCP Inspector or Claude Desktop, plus a voice page in the PWA (the rules allow a simulated Alexa+ experience)

## Ring API notes

There is no Ring SDK: everything is plain HTTPS to `https://api.amazonvision.com`. Ring's sample repo [AmazonAppDev/ring-api-helloworld](https://github.com/AmazonAppDev/ring-api-helloworld) (MIT, Next.js + Python) handles tokens, webhooks and live video and is our starting point.

| Purpose | Call | Notes |
| --- | --- | --- |
| Devices | `GET /v1/devices?include=status,capabilities` | First call on day 1 |
| Motion start/end | `GET /v1/history/devices/{id}/events?event_types=motion.human` | Only events after the account was linked |
| Clip | `POST /v1/devices/{id}/media/video/download` | `{timestamp, duration}`; ≤15 min, ≤1920×1080, 1–25 fps; existing footage only |
| Still image | `POST /v1/devices/{id}/media/image/download` | `{type:"at_timestamp", timestamp}`; nearest frame within ±10 s; ≤1080p |
| Live video (fallback) | `POST …/media/streaming/whep/sessions`, `DELETE …/{session_id}` | WebRTC, video only; max 60 s on plug-in cameras |
| Subscription | `GET /v1/accounts/me/subscriptions` | Trial or paid |

Both downloads answer `303` with a temporary link to the file.

**Access**

- Developer Playground (developer.amazon.com/ring/console/playground) gives a \~30-minute token with no app setup — use it on day 1.
- The private app needs three public HTTPS URLs: Account Link URL (a sign-in form), Token Exchange URL, Webhook URL (required even if unused).
- Use one-way account linking (Ring's recommended method). Access tokens last 4 h, refresh tokens \~30 days.
- Rate limit: 100 requests per second.
- Private apps: up to 5 linked Ring accounts, no certification, no country restrictions. Each account needs a Ring plan or trial.

**Webhooks**

- Verify `X-Signature` (HMAC-SHA256 of the raw body, hex, prefixed `sha256=`) before anything else.
- Reply 200 within 5 seconds; do the work from a queue.
- 5xx = Ring retries (6 times, 1 s to 1 h); 4xx = no retry, and 10+ in a row can disable the webhook.
- Skip repeats by `meta.request_id`. Only process `motion_detected` with `subType: human`.
- Contact-sensor events (`contact_sensor_faulted` / `_cleared`) are webhook-only, never in event history — store them on arrival.

**Gotchas**

- Footage before the account was linked is refused (`TIME_RANGE_NOT_AUTHORIZED`). Link first, then record demo footage.
- If Motion Recording is off or Smart Alerts filter the motion, no events and no clips arrive. Our app cannot change these settings.
- Our screens never appear inside the Ring app. Ring shows the listing and install steps, then opens our sign-in page in a browser; after that the user uses our PWA.

## Analysis with Bedrock Nova

Nova returns only what changed in each opening; the inventory is the running total of those changes, and the user confirms anything Nova is unsure of.

**Input per opening**

- The MP4 for the motion window, at a low frame rate (start around 5 fps)
- 3–4 stills from the moments the door is open, which are sharper than video frames
- Only openings that pass the open/closed check are analyzed

**Output format**

```json
{
  "door_opened_at": "2026-10-16T18:02:11Z",
  "door_closed_at": "2026-10-16T18:02:40Z",
  "added":   [{"item": "eggs", "category": "dairy", "quantity": 12, "confidence": 0.86}],
  "removed": [{"item": "chocolate bar", "category": "snack", "quantity": 1, "confidence": 0.62}]
}
```

**Accuracy**

- Aim for item types (eggs, milk, chocolate, soda can), not brands, flavours or expiry dates. At \~2 m a chocolate bar is only \~45 px wide.
- Below a confidence cutoff (start at 0.7), the PWA asks the user to confirm or correct.
- Camera placement matters more than the model: about 1–1.5 m away, angled into the fridge.

**Door open/closed check**

Compare brightness in a fixed box over the door: the fridge light makes "open" obvious. This runs before Nova and costs nothing. The contact sensor would replace it if we get one.

**Cost**

Log Nova's cost for every clip from day 1. A household opens the fridge about 20–40 times a day, so cost per clip decides any future price. Test with phone-recorded 1080p clips in the Bedrock console before the camera arrives.

## Reference images

Users teach the app their own items with photos (a pizza box, a yogurt drink, a favourite snack), and Nova compares each opening against them. This turns "a box" into "Dr. Oetker pizza" for the things a household actually buys.

**How it works**

1. In the PWA, the user adds an item to **My items**: name, category, and 1–3 photos.
2. The best photo is a **still from the fridge camera itself**: same angle, distance and lighting as real openings. When the user corrects a wrong guess, the PWA offers "Save this as a reference for *Greek yogurt drink*".
3. Phone photos are accepted too, as a quick start.
4. For each opening, the analysis request includes the camera stills plus a short list of reference images, and the prompt asks Nova to name catalog items when they match.
5. Nova's output names the catalog item when it matches: `{"item": "Greek yogurt drink", "catalog_id": "itm_042", "confidence": 0.91}`. Unmatched items fall back to a generic name and category.

**Keeping requests small**

- Send at most \~10 reference images per request: items currently in the fridge (likely to come out) plus the most frequently seen items (likely to go in).
- Resize references to about 512 px on the long side.
- Stretch goal: match by image embeddings (e.g. a multimodal embeddings model on Bedrock) to pick the closest references, so the catalog can grow without making requests bigger.

**Storage**

- Photos in S3 under the user's own folder; catalog entries in DynamoDB (item id, name, category, photo keys).
- Reference photos are kept until the user deletes the item. Unlike raw clips, they are not auto-deleted. "Delete my data" removes them.

**To check**

- [ ] Whether Nova accepts a video and images in the same request. If not, send stills + reference images only (all images), which is the plan anyway.
- [ ] Nova's limit on images per request, and the cost of \~10 extra images per opening.
- [ ] Accuracy with and without references: run the same 10 test openings both ways and record the difference. It's a strong number for the demo and write-up.

## Schedule

&#91;embedded content: schedule · Oct 14–23, one bar per working day\]

Ring access goes first because everything depends on it. Fire TV is built on Oct 21 only if the pipeline, PWA and MCP server all work by the end of Oct 20; otherwise that day goes to polish and the open-source client. Reference images add about half a day, split between the clip pipeline (Oct 17–18) and the PWA (Oct 19).

## Keeping a Ring Appstore launch possible

Publishing is decided after the hackathon. These cheap choices now avoid a rewrite later; nothing else for publishing is built this week.

| Choice now | Why |
| --- | --- |
| Credentials in config, never in code | A private app can't become public; a public launch is a new app with new credentials, same backend |
| One-way account linking with a real sign-in (e.g. Amazon Cognito) | Required for public apps; the private app needs a sign-in page anyway |
| Store everything by Ring `account_id` and device ID | Multi-user later without a data migration |
| Handle `app_integration_removed`, `device_removed`, `subscription_deactivated` | Certification checks them; about 20 lines each |
| Crop to the fridge, auto-delete raw clips, a "delete my data" option | Ring's privacy questionnaire asks; also a selling point |
| The name FridgeSense, with no "Ring", "Amazon" or "Alexa" | Ring branding rule |
| Main repo private, shared with judges | Keeps the product from being copied; a small Ring client is open-sourced separately |

For reference, if published: monthly subscription through Ring's billing only, Ring keeps 10%, US customers only for now, certification required. Ring's UX guide expects a web app, WCAG 2.2 AA, subscription status, data deletion, and notifications capped around once a day.

## Risks and open questions

The biggest risk is Ring developer setup eating days 1–2; it goes first, before any other code.

| Risk | Fallback |
| --- | --- |
| Ring registration or account linking is slow | Build against Playground tokens; finish linking in parallel |
| Motion recording is too short to cover a whole opening | Start a live session on the motion event to force recording (60 s max per session) |
| Nova misidentifies items | Stills plus video, confidence cutoff, user confirmation in the PWA |
| Camera placement gives a poor view | Top of upper cabinets at \~45° into the fridge, 1–1.5 m away |
| Scope creep across tracks | Fire TV only if Ring + Alexa+ work by Oct 20 |
| AWS costs (no credits left) | Budget alarm; low frame rates; analyze only real openings |

**Open questions**

- [ ] Is there a Ring sandbox with synthetic devices we can use before the camera arrives? Ring's glossary mentions one; no instructions found. Ask on the hackathon forum.
- [ ] How long is a motion recording on this camera, and does one cover a full fridge opening?
- [ ] Does the contact sensor need a Ring Alarm base station?
- [ ] Entering as an individual or as a company?
- [ ] Is "FridgeSense" free to use (trademark, domain, app stores)? "Sense" is also the brand of a well-known home energy monitor.

## Submission checklist

All of this is due on Devpost by Oct 23, 12:00 pm PT; aim to submit on Oct 22.

- [ ] Text description of features and how it works
- [ ] Tracks selected: Ring, Alexa+ (and Fire TV if built); mini challenges: AWS Builder, Open Source
- [ ] Repo URL with setup and run instructions; private repo shared with testing@devpost.com and the Amazon reviewers listed in the rules
- [ ] Demo video under 3 minutes on YouTube or Vimeo: the real camera, a real fridge opening, the inventory updating, an Alexa+ question answered
- [ ] No copyrighted music or third-party trademarks in the video
- [ ] Product feedback for each tool: Ring API, Bedrock Nova, Strands, MCP — including which AWS services were used and how
- [ ] Open Source: contribution URL, repo URL, GitHub username, what it does and why it matters
- [ ] Friction log entries (task, steps, expected vs actual, severity, workaround, suggestion)
- [ ] Optional feature requests with priority
