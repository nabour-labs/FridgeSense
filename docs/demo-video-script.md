# Demo video script

Rules: under 3:00, public on YouTube or Vimeo, shows the project running on the real device, no copyrighted music ([hackathon-plan.md](hackathon-plan.md#hackathon-rules-that-matter)). The video must pass three fit checks: a **real Ring camera seeing a real door opening**, **an Alexa+ question answered**, and **the AWS services at work** ([submission-checklist.md](submission-checklist.md), §1 and §3).

Target length 2:45, about 380 spoken words.

## Scenes

| # | Time | On screen | Voiceover |
| --- | --- | --- | --- |
| 1 | 0:00–0:10 | Close-up: a hand puts a can of beer in the fridge, door closes | "You're at the store. Do you have beer at home? Most people guess." |
| 2 | 0:10–0:25 | Wide shot of the Ring Indoor Cam 2K aimed at the fridge, then the FridgeSense Fridge screen on the phone | "FridgeSense turns a Ring Indoor Cam into a fridge that knows what's inside. No scales, no barcodes, no typing." |
| 3 | 0:25–0:55 | **Real run.** Split screen: fridge left, phone Activity screen right. Open the door, put the beer in, close it. Clock on screen, speed up the wait (label "≈1 min later"), then the new card with the **+ beer** proof still | "Each time the door opens, Ring sends a webhook. FridgeSense pulls the clip, checks the door really opened, and asks Amazon Nova what went in or out. About a minute later the beer is in my inventory, with a photo as proof." |
| 4 | 0:55–1:05 | Fridge screen: beer under Beverage, "added 1 min ago" | "The inventory stays current without me doing anything." |
| 5 | 1:05–1:30 | **Alexa+:** "Alexa, do I have beer?" and the answer (see [Alexa+ path](#alexa-path)) | "And I can just ask." *(let the answer play)* "Alexa+ talks to FridgeSense through an MCP server with six tools: find an item, list the inventory, what's running low, what to eat first, and door activity." |
| 6 | 1:30–2:05 | Architecture diagram, then the AWS console: one Step Functions execution graph (all green), then a Debug trace showing Nova tokens and cost | "Under the hood: API Gateway and Lambda check Ring's signature and reply right away. Step Functions downloads the clip, runs a pixel door check, so motion without an opening costs nothing, crops and face-blurs the stills with Rekognition, then sends them to Nova 2 Lite. Results go to DynamoDB, which the app and the MCP server both read." |
| 7 | 2:05–2:25 | Quick cuts: Review screen (confirm a low-confidence item), Stats heatmap, Ask "What should I eat first?", 3 s of the Fire TV kitchen view | "When Nova isn't sure, it asks me instead of guessing. I get door stats, a nudge to eat what's been there longest so less food goes to waste, and a kitchen dashboard on the TV." |
| 8 | 2:25–2:40 | A face-blurred still, the Pause switch, cost figure on screen | "Privacy is built in: faces are blurred before anything is stored, raw images are deleted after 7 days, and you can pause it with one switch. Each door opening costs about a fifth of a cent." |
| 9 | 2:40–2:50 | Name, tagline, repo URL | "FridgeSense. Know what's in your fridge without opening it." |

### Alexa+ path

Pending the MCP Toolkit attempt in [submission-checklist.md](submission-checklist.md) §1:

- **Toolkit works** (`alexa-ai deploy`): record the real question in the Alexa+ add-ons simulator or on an Echo.
- **Toolkit gated:** use the **Ask** screen (mic → "Do I have beer?" → Polly reads the answer), then 5 s of Claude Desktop calling the same MCP server. Say it plainly: "Alexa+ toolkit access is pending, so this is the same MCP server through a stand-in client." Repeat that in the Devpost description.

## Shot list (recording order)

1. **Rehearse.** 2–3 openings; each shows on Activity with the right item. **Blur faces** on. Do Not Disturb on phone and Mac.
2. **Real run (scene 3) first,** while the pipeline is warm. Fridge on a tripod-mounted second phone or camera; phone screen recorded at the same moment. Two takes.
3. **Phone screens,** about 10 s each: Fridge, Review, Stats, Ask, Config → Pause.
4. **Mac screens:** the Step Functions execution from that run, its Debug trace, the architecture diagram, Claude Desktop or MCP Inspector.
5. **Fridge B-roll:** beer close-up, wide shot of the camera.
6. **Voiceover last,** read over the rough cut, then trim to fit.

Never on screen:

- The MCP URL (it contains the secret key)
- `.env` or anything from Secrets Manager
- Livestream (not face-blurred)
- Other people's faces
- The AWS account ID (crop it)

## Software (Mac)

| Job | Tool |
| --- | --- |
| Phone screen capture | QuickTime → File → New Movie Recording → pick the iPhone from the dropdown by the record button (USB cable). Backup: iPhone Control Center screen recording |
| Mac screen capture | Cmd+Shift+5, select a region. Optional: Screen Studio (paid) for auto-zoom on clicks |
| Editing | iMovie (side-by-side, picture-in-picture, titles, speed-up, voiceover). DaVinci Resolve (free) for callouts, zooms and burned-in captions |
| Voiceover | iMovie voiceover or QuickTime → New Audio Recording; a USB mic beats AirPods; quiet, soft-furnished room |
| Diagram | Paste the README mermaid block into mermaid.live, export PNG |
| Music | None, or iMovie soundtracks / YouTube Audio Library (royalty-free), kept quiet |
| Captions | YouTube auto-captions after upload; fix Nova, MCP, FridgeSense |
| Upload | YouTube, **Public**; check the link in a private window; add it to the top of the README |
