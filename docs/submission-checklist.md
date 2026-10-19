# Submission checklist

Devpost deadline: **Fri Oct 23 2026, 12:00 pm PT**. Target: submit **Thu Oct 22**. Rules: [amazonappdev2026.devpost.com/rules](https://amazonappdev2026.devpost.com/rules) (summary in [hackathon-plan.md](hackathon-plan.md#hackathon-rules-that-matter)).

Entering: **Ring** and **Alexa+** tracks, **AWS Builder** mini challenge. Open Source mini, Fire TV and Bee are cut (see the plan's Demo MVP scope).

State as of Oct 17: repo is public on GitHub with an MIT license; `main` has the same content as `local`; the `FridgeSense` stack is deployed (`UPDATE_COMPLETE`, Oct 17). Items marked ✅ are already true.

## 1. Fit checks (pass/fail, must hold before anything else)

- [ ] **Ring:** the video shows the real Ring Indoor Cam 2K and a real door opening flowing through the Ring APIs (webhook → history → clip/stills download) at runtime
- [ ] **Alexa+:** decide how Alexa+ appears in the video. The MCP Toolkit looked gated on Oct 14 ([friction log](friction-log.md)):
  - [ ] Try `alexa-ai configure` / `alexa-ai new mcp` / `alexa-ai deploy` (README, "Alexa+ (MCP Toolkit)"). If it works, record "Alexa, do I have milk?" in the simulator or on an Echo
  - [ ] Otherwise use the fallback the rules allow (a simulated Alexa+ experience): the **Ask** screen (Nova as MCP client + Polly voice), plus MCP Inspector or Claude Desktop calling the same server. Say so plainly in the description
  - [ ] Confirm the MCP server reports spec 2025-11-25 over Streamable HTTP (MCP Inspector → Connect → List Tools)
- [ ] **AWS Builder:** description and feedback name the AWS services and how each is used (see §4)

## 2. Live system ready for judges (judging Nov 9–20)

- [ ] Set `demo_passcode` in `fridgesense/ring-app` (README, "Demo access"). Currently **not set** (secret has only `client_id`, `client_secret`, `hmac_key`, `mcp_key`, `passcode`, `user_passcode`)
- [ ] Replace the README placeholders `<SiteUrl>` and `<demo passcode>` in "Try it (judges)" and remove the TODO note. Decide whether the demo passcode goes in the public README or only in the Devpost "testing instructions" field
- [ ] Sign in with the demo passcode on a phone: Fridge, Activity, Stats, Ask all show data; editing is disabled; "Demo · read-only" badge visible
- [x] **Live view privacy:** live video is not face-blurred, so **Livestream** is owner-only: the button is hidden for the user and demo passcodes, and the live routes answer them 403
- [x] Debug traces: off by default when deployed (`-c debugTraces=true` turns them on), and while **Blur faces** is on they keep only blurred 160 px thumbnails. Keep **Blur faces** on for recording and judging
- [x] Ring plan stays active through **Nov 20**: Jayson subscribed monthly (Oct 18), so it no longer depends on the trial
- [ ] Keep using the fridge normally during judging so the 7-day Activity and stills are never empty
- [ ] Ring token refresh is healthy: `uv run fridgesense-devices` lists the camera; no `token_refresh_rejected` in logs
- [ ] AWS budget alert confirmed (SNS subscription email clicked); `askAgentDailyLimit` sensible for judge traffic
- [ ] Final `cdk diff` shows nothing undeployed after the last merge (ask Jayson before any deploy)

## 3. Demo video (< 3 min, public on YouTube or Vimeo)

- [ ] Script follows the plan's one-liner: milk into the fridge → inventory updates on the phone within a minute → "do I have milk?" → "Yes, 1 milk, added 2 minutes ago"
- [ ] Shows the real camera and a real fridge opening (Ring fit check), the Alexa+ path from §1 (Alexa+ fit check), and briefly the AWS architecture: Step Functions run, Nova, Rekognition blur (AWS Builder)
- [ ] Optional beats for the judging criteria: Review screen for low-confidence items, Stats (opens per day, by hour, open time), cost per opening (~$0.0014 Nova + ~$0.001/still face blur), privacy (face blur, 7-day expiry, crop)
- [ ] No copyrighted music; no third-party logos or trademarks beyond what the tracks require; no unblurred faces of other people
- [ ] Under 3:00, uploaded **public** (or unlisted if the rules allow; check), link opens in a private window

## 4. Devpost write-up

- [ ] Project name **FridgeSense** (no "Ring", "Amazon" or "Alexa" in the name), tagline, thumbnail (README screenshots in `docs/screenshots/`)
- [ ] Description: problem, what it does, how it works (webhook → Step Functions → clip door check → stills → face blur → Nova → DynamoDB → PWA / MCP), what's novel (non-security Ring use), cost per opening, privacy choices, what's next
- [ ] Tracks selected: Ring, Alexa+; mini challenge: AWS Builder
- [ ] Built with: Ring Partner API, Amazon Bedrock (Nova 2 Lite), AWS Lambda, Step Functions, API Gateway HTTP API, DynamoDB, S3, CloudFront, Secrets Manager, Rekognition, Polly, CloudWatch, SNS, AWS Budgets, AWS CDK, MCP Python SDK, Python 3.13, React, Vite, Tailwind, Recharts
- [ ] Repo URL: <https://github.com/nabour-labs/FridgeSense> ✅ public, MIT ✅, setup and run instructions in README ✅
- [ ] Testing instructions for judges: app URL, demo passcode, what to try, and that the MCP URL is available on request (it is a secret)
- [ ] **Product feedback (required)** for each tool/API/SDK used: what worked, what needs work, onboarding, would you build with it again. Drafted in [product-feedback.md](product-feedback.md); the Alexa+ section waits on the MCP Toolkit attempt in §1. Covers:
  - [ ] Ring Partner API (account linking, token exchange, webhooks, media download, live WHEP)
  - [ ] Alexa+ / MCP Toolkit (access, docs)
  - [ ] Amazon Bedrock Nova 2 Lite (Converse, tool use, prompt caching, no structured outputs, cross-region profile)
  - [ ] MCP Python SDK (v2 changes, Lambda)
  - [ ] AWS CDK and the other AWS services listed above, Rekognition and Polly included
  - [ ] Strands Agents: mention only if used; the Ask agent uses Bedrock Converse tool use (Strands clashed with `mcp` 2.3, see friction log)
- [ ] **Friction log (optional, up to 10% bonus):** [friction-log.md](friction-log.md) has 24 entries ✅. Before submitting, skim that each has task, steps, expected vs actual, severity, workaround, suggestion, and paste or link it in the form
- [ ] Optional feature requests with priority (good sources: friction-log "Suggestion" lines)
- [ ] Entrant type decided (individual vs Nabour Labs as an organization); entrant is not a Quebec resident or Quebec-based organization

## 5. Repo hygiene (before the last release PR)

- [x] The seven open OpenSpec changes were archived Oct 17 ✅. Live post-deploy checks are still open in their archived tasks: `camera-livestream` (5.3), `door-check-blue-light` (1.1, 7.1, 7.3), `door-zone-setup` (1.1, 8.2), `fridge-crop-box` (4.3), `pipeline-debug-traces` (8.4). Run them after the next deploy if time allows. Archive any new changes before the last release
- [ ] All tests green locally: `backend` (`uv run pytest && uv run ruff check`), `infra` (`npm test`), `pwa` (`npm test`); `unit-tests` check green on the release PR
- [ ] No secrets, `.env`, clips or unblurred stills in git ✅ (`git ls-files` shows none; `tmp/` and `*.mp4` are ignored). Re-check after the last commit
- [ ] README: remove or update anything stale (e.g. "Nothing uses it yet" for Fridge area if crop lands), add the video link at the top
- [ ] Final release branch `release/<date>` from `local` → PR to `main` (Jayson's OK) → merged by Jayson
- [ ] Optional: add GitHub topics (`ring`, `alexa`, `mcp`, `amazon-bedrock`, `aws-cdk`)

## 6. Submit

- [ ] Fill every required Devpost field, preview, submit by **Oct 22**
- [ ] After submitting: open the Devpost page logged out; video plays, repo and app links work
- [ ] After judging (Nov 20+): remove `demo_passcode`, rotate `mcp_key`, decide whether to keep the stack running (`cdk destroy` keeps the table and secret)
