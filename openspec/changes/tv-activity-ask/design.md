# Design

## Context

- **The dashboard.** `pwa/src/tv/TvDashboard.tsx` is a thin UI over pure helpers in `pwa/src/tv/tv.ts`. It polls three things with `useLoad`: inventory every 10 s, `events(28)` every 30 s and the camera every 5 min. It has no keys, no focusable elements and `cursor: none` on its root. The header's latest still is `LatestStill`/`StillFigure` plus `latestStill()` in `tv.ts`. Proof photos use `Photo` and `useStillSrc`, which keeps the first presigned link per `stillBase`.
- **The Ask screen.** `pwa/src/screens/Ask.tsx` has a private `Recognizer` type, `recognizerClass()` (`SpeechRecognition ?? webkitSpeechRecognition`), a listen/stop toggle and `say(answer, audio)`. `say` plays a `data:audio/mpeg;base64` source in one `<audio>` element and falls back to `speechSynthesis`.
- **The ask endpoint.** `POST /api/ask` (`api.ask(question)`) has no `write` or `owner` flag, so the TV's viewer session can call it.
- **The Fire TV app.** `firetv/` is a full-screen `WebView` with `allowSystemKeyEvents`, `domStorageEnabled` and `hasTVPreferredFocus`. Its manifest leaves out the template's media, audio and DRM services ("plays no media") and declares no icon.
- **Remote input on the device.** Jayson's screenshot on the Vega Virtual Device (2026-10-20) shows the remote's teal pointer over the panels, despite `cursor: none`. The WebView is in pointer mode, and it is not yet known whether D-pad presses reach the page as arrow keys.
- **Spec base.** `tv-dashboard-more` and `tv-proof-photos` are code-complete but unarchived. Their last tasks are the on-device check, which that screenshot covers.

## Goals / Non-Goals

**Goals:**
- Paging, the Activity page and the voice flow are testable in Vitest with a fake recognizer and a fake `api`.
- One copy of the speech and audio code, shared by the Ask screen and the TV.
- The overview layout keeps its current look apart from the header.

**Non-Goals:**
- Making the Vega pointer disappear (logged as friction, not fixed here).
- Any backend change.

## Decisions

1. **Archive the two TV changes first (task group 0).** `tv-dashboard-more`'s check 3.1 (🧂, camera line, heatmap) passed on the screenshot. Its "no cursor" part failed: the pointer still shows, so log the friction entry its design decision 6 calls for. `tv-proof-photos` 4.2 (proof photos and latest still) passed too. Archive both so this change's MODIFIED and REMOVED requirements have a base. *Alternative:* write this change's deltas against the unarchived deltas. OpenSpec merges deltas only against `openspec/specs/`, so the result would be wrong.

2. **The page is component state, switched by a `keydown` listener on `window`.** `ArrowRight`/`ArrowLeft` call `preventDefault()` and set `page`. Every other key, Escape included, is left alone. Both pages render from the same `useLoad` results, so switching pages makes no requests. The overview grid and the Activity panel are swapped in place, with the header outside both. *Alternative:* a horizontal scroll container with CSS scroll-snap. Arrow-key scrolling inside a Vega WebView is unverified, and scroll position is harder to assert in jsdom than state.

3. **A fallback for pointer mode: the page indicator is plain text, not buttons.** The specs allow only the mic button. If on-device testing (task 6.2) shows that D-pad presses move the pointer instead of sending arrow keys, the fallback is for the app to pass the keys through. Vega's WebView `allowSystemKeyEvents` is already on, and the next thing to try is the Vega pointer/navigation mode setting. That would be a `firetv-app` follow-up, logged as friction, without changing the dashboard's behaviour.

4. **Activity rows come from a new pure helper `activityRows(events, now, tz)` in `tv.ts`.** It mirrors `recentRows`, with three differences: it never merges no-change runs, it gives a day label instead of "11 h ago", and it adds `stills.slice(0, 4)`. It reuses the proof selection `recentRows` already does (first `proof` link per non-rejected change, at most 3), factored into one shared function. Pictures use the existing `Photo`/`useStillSrc`, so broken-link hiding and re-signed links work as they do for proof photos. The rows go in a two-column, top-to-bottom layout, and a row that doesn't fit is clipped (`overflow-hidden`), as on Recent changes.

5. **Move the speech code to `pwa/src/voice.ts`.** It holds the `Recognizer` type, `recognizerClass()`, `speak()`, and a `playAnswer(el, answer, audio)` that is today's `say` logic. `Ask.tsx` imports it unchanged in behaviour, and its existing tests are the guard. The TV gets a small `useVoiceQuestion(api)` hook: it holds the state (`idle | listening | thinking | answered | error`), the question, the answer, a 20 s hide timer and the listen/stop toggle. *Alternative:* render the Ask screen inside the TV. Its layout, history and text box don't suit a TV, and the box would break the "no inputs" rule.

6. **Mic focus with `autoFocus` on the button, and a visible focus ring** (`focus-visible:ring-4`). The remote's select then fires a click without any key code handling. Arrow keys still page, because the listener is on `window` and calls `preventDefault()`, which also stops the browser moving focus. Escape is untouched.

7. **The answer banner is a fixed strip between the header and the pages, with `aria-live="polite"`.** It shows on both pages and leaves the panels' content alone. It shrinks the page area for up to 20 s.

8. **Fire TV icon.** Copy `pwa/public/icon-512.png` into the `firetv/` package. Declare it in `manifest.toml`'s `[package]` section using the form the Vega manifest validator accepts. The local SDK has no sample, so task 5.2 confirms the exact key and path with `vega` build output; the spec only asks that the warning goes away. A Jest test in `firetv/test/` checks the manifest entry and that the file matches the PWA's byte for byte.

9. **Audio and microphone in the WebView.** Answer audio plays after a remote press, which counts as a user gesture, so no autoplay setting should be needed. If on device it does not play, put back the template's audio service in `[wants]` and/or set the WebView's media props (task 6.2). Speech recognition on Vega's WebView is unknown. If `SpeechRecognition` is missing there, the spec'd behaviour is that no button shows. Log that in the friction log rather than building an alternative (Jayson chose speech-only, 2026-10-20).

## Risks / Trade-offs

- [D-pad presses don't reach the page as arrow keys in pointer mode] → Decision 3's follow-up. The overview still works as today, and Activity is unreachable until it's fixed. Checked in task 6.2 before archiving.
- [Vega WebView has no speech recognition] → The mic is hidden by design. The demo then shows voice on the phone. Log it as friction.
- [Microphone permission prompt inside the WebView] → If one appears and can't be answered with the remote, log it. Granting it in the manifest is a follow-up.
- [Removing the latest still reverses a requirement added two days ago] → Removed explicitly with a reason, so the spec history explains it.
- [Each question costs a Nova call and a Polly clip] → Only on a button press, the same as the phone. The cost per call is already logged by the assistant.

## Migration Plan

1. Archive `tv-dashboard-more` and `tv-proof-photos` (with Jayson's OK on the on-device results), then implement and test this change.
2. Deploy the PWA (ask first). The TV picks up the dashboard changes on its next load.
3. Rebuild and sideload the Fire TV app for the icon (and any audio/mic settings).
4. Rollback: redeploy the previous PWA. The old app build still works against it.

## Test strategy

- **Unit (Vitest, `pwa/src/tv/tv.test.ts`):** `activityRows`: day label, clock time, duration, labels, "Checking…" and "No changes", 4-still cap, proof selection and cap, no merging of no-change runs, the 7-day cutoff, empty input. The old `latestStill` tests are deleted with the requirement.
- **Component (Vitest + Testing Library, `pwa/src/tv/TvDashboard.test.tsx`):**
  - icon in the header;
  - paging with `fireEvent.keyDown(window, {key: "ArrowRight"})`, `defaultPrevented`, `aria-current`, no extra API calls;
  - Activity panel rows, "No Data" and the empty text;
  - Escape untouched;
  - only the mic button, and only icon/still/proof `img`s;
  - the voice flow with a fake recognizer class on `window.SpeechRecognition` (start options, final result, `api.ask` body, answer banner, audio `src` on a stubbed `HTMLMediaElement.prototype.play`, `speechSynthesis` fallback, stop, not heard, failure);
  - the 20 s banner timer with fake timers;
  - no mic when the recognizer is absent;
  - mic focus.
  - Existing tests for the latest still are removed with the requirement, and the rest stay.
- **Regression:** `pwa/src/screens/Ask.test.tsx` passes unchanged after the move to `voice.ts`.
- **Fire TV (Jest, `firetv/test/`):** the manifest has an icon entry, the file exists, and it is byte-equal to `pwa/public/icon-512.png`.
- **Manual (not automated):** browser preview at 1920×1080 with the mock API, then the Vega Virtual Device against the deployed site: paging with the remote, the mic button (or its absence), answer audio and the launcher icon.
- **Stubbed:** all API calls (fake `api`), speech recognition, audio playback and speech synthesis. No live Bedrock, Polly or Ring.
