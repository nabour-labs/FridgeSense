# Proposal

## Why

The kitchen TV dashboard runs on the Vega Virtual Device with live data. Jayson checked it on 2026-10-20 and wants it to do more than show numbers: browse recent door openings, ask the fridge a question out loud, and look like the same product as the phone app. The header's latest still adds little next to the proof photos, and it takes space the new controls need.

## What Changes

- **Latest still removed.** The header no longer shows "Latest still · <time>" or its picture. **BREAKING** for the `tv-dashboard` spec: the "Latest still in the header" requirement from `tv-proof-photos` is removed.
- **App icon in the header.** The PWA's app icon (`/icon.svg`) sits left of the "FridgeSense" title.
- **Activity page.** The dashboard gets a second page, reached with the remote's Right button; Left goes back to the overview. Each door opening shows its time, how long the door was open, what changed, its stills and its proof photos. No video. A page indicator ("Overview · Activity") shows which page is on screen.
- **Ask by voice.** A microphone button in the header listens with the browser's speech recognition, sends what it heard to `POST /api/ask`, shows the question and answer on screen and plays the answer's voice audio. If the WebView has no speech recognition, the button is not shown, as on the PWA's Ask screen.
- **Rules relaxed for these controls.** The TV dashboard may now have the microphone button and call `POST /api/ask` after a spoken question. It still shows no clips, video, live view or camera snapshots, and still leaves Back to the Fire TV app.
- **Launcher icon.** The Fire TV app gets the same icon as the PWA, instead of the system default.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tv-dashboard`: remove the header's latest still; add the title icon, the Activity page with remote paging, and voice questions; relax "Nothing private or interactive on the TV dashboard" for the mic button and `POST /api/ask`; drop the latest still from "Photos load quietly".
- `firetv-app`: the app declares a launcher icon that is the PWA's icon.

## Hackathon tracks

Fire TV (the kitchen dashboard on a Vega OS TV). Alexa+-style voice questions come from the same `/api/ask` assistant that uses the MCP server.

## Out of scope

- Playing clips or live view on the TV.
- Using the remote's own microphone button: Fire TV gives that button to Alexa, so the app can't capture it.
- A typed question box or preset questions when speech recognition is missing.
- Deleting openings or any other edit from the TV.
- More than two pages, or paging within the Activity page.

## Impact

- **PWA:** `pwa/src/tv/TvDashboard.tsx` (header icon and mic, two pages, Activity page, answer banner); `pwa/src/tv/tv.ts` (helpers for Activity rows; `latestStill` removed); the speech recognizer type and "play the answer" code move out of `screens/Ask.tsx` into a shared module so the TV and Ask screens use the same code. Tests: `pwa/src/tv/TvDashboard.test.tsx`, `pwa/src/tv/tv.test.ts`, `pwa/src/screens/Ask.test.tsx` must stay green.
- **Fire TV app:** `firetv/manifest.toml` (icon, and audio/microphone settings if the device needs them), an icon file copied from `pwa/public/icon-512.png`, and maybe WebView media props in `firetv/src/App.tsx`. Rebuild and sideload.
- **Backend:** none. `POST /api/ask` already accepts viewer sessions.
- **Cost:** each spoken question is one `/api/ask` call: Nova on Bedrock plus a short Polly clip, as on the phone. Nothing runs unless someone presses the mic.
- **Depends on:** `tv-dashboard-more` and `tv-proof-photos` being archived first, since this change modifies and removes requirements they add.
