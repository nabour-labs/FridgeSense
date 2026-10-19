# Proposal

## Why

The fridge sits in the kitchen and so, often, does a TV. Today FridgeSense is only on the phone: to see what is in the fridge or what just changed, someone has to unlock a phone and open the app. A Fire TV app turns any TV in the room into a glanceable kitchen dashboard: what is in the fridge, what the last few door openings added or removed, and how often the fridge was opened today. It also lets FridgeSense enter the hackathon's Fire TV track, which takes any app built with web technologies that runs on Fire OS or Vega OS, shown in the demo video on a real Fire TV or the Fire TV/Vega simulator.

The PWA already has every piece of data and logic this needs. The cheapest path is a read-only TV view inside the PWA, plus a thin Fire TV app that only hosts it in a WebView, about one day of work in total.

## What Changes

- **TV dashboard in the PWA.** Opening the app at `#tv` shows a single read-only screen built for a 1920×1080 TV seen from across the room, instead of the tabbed phone app. It has three panels:
  - **In the fridge:** in-stock items grouped by category with icon, name and quantity; out-of-stock items are left out; at most 12 items are shown, then "+N more".
  - **Recent changes:** the 5 newest door openings of the last 7 days, each with how long ago it happened and its added/removed items ("Checking…" while analysis runs).
  - **Opens:** today's open count and a 7-day bar chart, computed with the existing `stats.ts` helpers.
  Inventory refreshes every 10 s and openings every 30 s while the page is visible. A panel whose data fails to load shows "No Data" on its own; the others keep working.
- **No photos, no controls.** The TV dashboard shows no stills, clips, live view or camera pictures, and has nothing to tap or select: it is safe to leave on in a shared room. It calls only `GET /api/inventory` and `GET /api/events`, so it works with every role, including the read-only viewer passcode.
- **Sign-in with a remote.** At `#tv` with no session, the existing passcode screen is shown; its passcode field is already focused on load, so the TV's on-screen keyboard opens at once and Enter signs in. After signing in the app stays on `#tv`. The session is kept in the WebView's storage as today, and expiry or a 401 returns to the passcode screen.
- **Fire TV app (Vega OS).** A new `firetv/` package: a Vega OS React Native app whose only screen is a full-screen `@amazon-devices/webview` `WebView` loading `<site URL>#tv`, with DOM storage on, system keys (Back) passed to the page and initial focus on the WebView. The site URL is set at build time; no passcode or token is ever part of the app. If the page can't load, the app shows "Can't reach FridgeSense" with a focused "Try again" button.
- **Fallback.** There is no Fire TV device, so the demo runs on the Vega Virtual Device (the Fire TV simulator) on the Mac. If it can't run there, the options are buying a Vega OS Fire TV stick or a Fire OS stick with an Android (Kotlin) WebView shell. There is no Fire OS simulator, and an Android TV emulator doesn't count as Fire TV. The TV dashboard doesn't change either way. design.md describes the switch.

Out of scope:
- Ask and voice questions on the TV, live camera view, editing the inventory, confirming pending changes, Config and Debug.
- Publishing to the Amazon Appstore, app icons beyond the template defaults, and Fire TV ambient/screensaver integration.
- A TV-specific sign-in such as a code shown on screen and confirmed on the phone.
- Infra changes: the TV dashboard ships in the existing PWA bundle on the existing CloudFront site.

Hackathon tracks: **Fire TV** (a Vega OS app built with web technologies, shown on the Vega Virtual Device or a Fire TV in the demo video). The plan only builds Fire TV once the Ring and Alexa+ demo works end to end, so this change is applied only after that.

## Capabilities

### New Capabilities

- `tv-dashboard`: the read-only `#tv` screen of the PWA: its panels, refresh, sign-in with a remote and what it never shows.
- `firetv-app`: the Fire TV (Vega OS) app that hosts the TV dashboard: what it loads, how it handles keys and load failures, and what it never contains.

## Impact

- PWA: new `pwa/src/tv/` (`TvDashboard.tsx` and its panels, `tv.ts` for the pure helpers), and a `#tv` branch in `App.tsx`. `screens/SignIn.tsx` already focuses the passcode field; a test pins that for the TV. No API or type changes.
- New `firetv/` package (Vega OS React Native app, `manifest.toml`, `src/App.tsx`, `src/site.ts`) with a `test` script, so the `unit-tests` workflow picks it up.
- Backend and infra: none.
- Docs: README gains a "Fire TV" section (build, sideload to the Vega Virtual Device or a Fire TV, sign in with the viewer passcode).
- Friction log: entries for any Vega SDK, Vega Virtual Device or Fire TV friction hit while applying.
- Cost: none beyond the existing API calls (one inventory read per 10 s and one events read per 30 s while a TV shows the dashboard).
