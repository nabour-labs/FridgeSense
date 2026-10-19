# Design

## Context

The PWA (`pwa/`, Vite + React + Tailwind + Recharts) already loads the inventory (`api.inventory()`, polled every 10 s on the Fridge screen) and door openings (`api.events(days)`), formats them (`format.ts`: `ago`, `changeLabel`, `titleCase`; `itemIcon.ts`) and counts opens per day (`stats.ts`: `perDay`, `todayCount`, `deviceTimeZone`). `useLoad` polls while the page is visible, keeps data across failed polls and reports errors to the shell, which signs out on a 401. Sign-in stores the session in `localStorage` (`session.ts`), and the passcode field already has `autoFocus`.

Fire TV now ships two platforms: Vega OS (React Native, new sticks) and Fire OS (Android, older sticks). Vega's `@amazon-devices/webview` hosts a web app with `source={{ uri }}`, `allowSystemKeyEvents` (Back arrives as `keyCode` 27) and `hasTVPreferredFocus`. The hackathon's Fire TV track accepts web technologies on either OS, shown on a device or the simulator.

## Goals / Non-Goals

**Goals:** a glanceable, read-only kitchen screen on a TV with no new backend; a Fire TV app thin enough that almost all logic and tests live in the PWA; a demo on the Vega Virtual Device.

**Non-Goals:** a native React Native rewrite of the screens, TV navigation between several screens, voice, editing, Appstore publishing.

## Decisions

### 1. The dashboard lives in the PWA, at `#tv`

`App.tsx` already routes by hash. After the session check, `#tv` renders `<TvDashboard />` inside the same `AppContext` instead of the header, tabs and debug bar. Same bundle, same sign-in, same `report` handling. A separate Vite entry or a second site was rejected: it would duplicate sign-in and deploy work for no gain.

Signing in at `#tv` keeps the hash (sign-in only swaps state, it never navigates), so the dashboard appears straight after.

### 2. Layout for 1920×1080 at a distance

One screen, no scrolling: a header ("FridgeSense" and the current time), then three panels in a row (In the fridge, wider; Recent changes; Opens). Text sizes start at `text-2xl` with item names at `text-3xl`; dark theme only (TVs in kitchens are often on at night). The 12-item cap and "+N more" keep the fridge panel from overflowing. Vega WebView renders at 1080p, so the layout targets a 1920 px viewport and scales down with `vw`-based gaps.

### 3. Pure helpers, thin components

`pwa/src/tv/tv.ts` holds the logic so it is unit-tested without rendering:

- `fridgeRows(items, max = 12) -> { groups: {category, items}[], more: number }`: in-stock only, `CATEGORIES` order, cap.
- `recentRows(events, n = 5) -> { id, ago, labels: string[], state: "checking" | "none" | "changes" }[]`: newest first, rejected changes dropped, labels from `changeLabel`.
- `opensSummary(events, now, tz) -> { today: number, days: DayCount[] }`: `todayCount` + `perDay`.

`TvDashboard.tsx` uses two `useLoad` calls (inventory at 10 s, `events(7)` at 30 s) and renders the three panels. Opens reuses the events load, so there are only two endpoints. Each panel shows `<NoData />` when its load `failed` with no data.

### 4. Nothing to focus, Back left alone

The dashboard renders no buttons, links or inputs and adds no key handlers, so D-pad keys do nothing and Back (`Escape`/27) reaches the Vega app, which exits. This also removes the need for a focus manager.

### 5. Fire TV app: Vega WebView shell

`firetv/` is created from the Vega SDK's basic React Native template. Its own code is two files:

- `src/site.ts`: `tvUrl(siteUrl: string | undefined): string`. It validates `https://`, strips any path hash and returns `<origin><path>#tv` (path normalized to end in `/`). The site URL comes from `firetv/site.config.json` (`{"siteUrl": "https://…"}`), written by hand from the `SiteUrl` deploy output. It is not a secret, but it is gitignored with a committed `site.config.example.json` so the repo doesn't point at one person's deployment.
- `src/App.tsx`: renders `<WebView source={{ uri: tvUrl(config.siteUrl) }} domStorageEnabled allowSystemKeyEvents hasTVPreferredFocus onError={…} />`, or the failure screen (`"Can't reach FridgeSense"` + a `Pressable` "Try again" with `hasTVPreferredFocus`) that bumps a `key` to remount the WebView.

`manifest.toml` keeps the template's defaults. No cleartext policy is needed because the site is HTTPS.

**Fallback.** There is no Fire TV device; the Vega Virtual Device is the only simulator that counts for the track (Amazon ships no Fire OS simulator, and an Android TV emulator is not Fire TV). If the Vega SDK or Vega Virtual Device doesn't work on the Mac within about 2 hours, stop and ask whether to buy a stick. With a Vega OS stick, nothing else changes. With a Fire OS stick, replace `firetv/` with an Android Studio "TV" project: one `Activity` with a full-screen `WebView` (`settings.domStorageEnabled = true`, `javaScriptEnabled = true`), the same URL rule in a Kotlin `tvUrl` with a JUnit test, and the same failure screen. Fire OS sticks take it by `adb install`. The PWA part doesn't change. Record the switch and its reason in the friction log.

### 6. No credentials in the TV app

The app ships with no passcode. Someone signs in once on the TV with the remote (the viewer passcode is the intended one for a shared screen), and the token lives in WebView storage until it expires (24 h), as on the phone. A TV-specific pairing flow is out of scope.

## Risks / Trade-offs

- **Vega SDK setup time** (about 20 GB, Rosetta on Apple Silicon, Vega Virtual Device support on macOS unconfirmed) → time-box to 2 hours, then use the Fire OS fallback.
- **CI installing Vega packages:** `npm ci` in `firetv/` must work on the GitHub runner. If the `@amazon-devices/*` packages can't install there, keep `tvUrl` in a dependency-free module tested by Vitest, and have the `test` script run only that (the component test then runs locally with the Vega toolchain).
- **Typing the passcode with a remote is slow:** it's once per 24 h. Acceptable for the demo.
- **24 h session on an always-on screen:** the dashboard falls back to the passcode screen daily. Acceptable; longer sessions are a separate change.
- **Burn-in on always-on TVs:** out of scope; most TVs dim on their own.

## Test strategy

- **Unit (Vitest, PWA):** `pwa/src/tv/tv.test.ts` covers `fridgeRows` ("Items by category", "More than fits", "Empty fridge"), `recentRows` ("Newest five", "Change labels", "Analysis running", "Quiet week") and `opensSummary` ("Today's count", "One opening today") with fixed `now` and `America/Toronto`.
- **Component (Vitest + Testing Library, PWA):** `pwa/src/tv/TvDashboard.test.tsx` uses `fakeApi` from `test-utils.tsx` and fake timers for "Inventory refresh"; covers the panels, "Events fail, inventory loads", "Stills not shown", "No controls", "Only two endpoints" (every other `fakeApi` method asserted uncalled) and "Back is left to the TV app". `pwa/src/App.test.tsx` covers "Open at #tv", "Other hashes unchanged", "Switch to #tv while open", "Session expired on the TV", "Field focused" and "Enter signs in to the dashboard".
- **Unit (firetv):** `firetv/src/site.test.ts` covers the URL scenarios. `firetv/src/App.test.tsx` (Jest + `react-test-renderer`, with `@amazon-devices/webview` mocked to a host component that records its props) covers "WebView settings", "Offline TV" and "Try again". `firetv/src/secrets.test.ts` scans `git ls-files firetv` for the patterns in "Source has no secrets".
- **Manual (recorded for the demo):** build with `vega build`, run on the Vega Virtual Device, sign in with the viewer passcode, open the fridge door and watch the panels update within about 30 s. "First launch" is checked here.
- Nothing calls live Ring, AWS or Bedrock: the PWA tests use `fakeApi`, and the firetv tests mock the WebView.
