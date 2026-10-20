# Tasks

## 0. Spec base

- [x] 0.1 With Jayson's OK on the 2026-10-20 Vega screenshot, tick `tv-dashboard-more` 3.1 and `tv-proof-photos` 4.2 (and its 0.1). Add a friction-log entry: the Vega remote pointer still shows over the dashboard despite `cursor: none`. Archive `tv-dashboard-more`, then `tv-proof-photos`. Verify: `openspec validate tv-activity-ask` passes, and `openspec/specs/tv-dashboard/spec.md` has "Latest still in the header" and "Photos load quietly". (`tv-proof-photos` had to re-add its privacy requirement as "Nothing private on the TV dashboard": a MODIFIED block can't drop a scenario.)

## 1. Header: remove the latest still, add the icon

- [x] 1.1 Write failing tests in `TvDashboard.test.tsx` for "Icon shown" and "Icon shown while data fails". Delete the latest-still tests in `TvDashboard.test.tsx` and `tv.test.ts`, along with the removed requirement ("Newest opening's last still", "Newest opening has no stills", "No stills at all", "Events fail" for the still, "Header still fails", "New picture replaces the old"). Run `npm test` in `pwa/`: the new tests fail because there is no icon
- [x] 1.2 Remove `LatestStill`, `StillFigure` and `latestStill()`, and add the `/icon.svg` image before the title. Verify: `npm test` in `pwa/` is green

## 2. Shared voice code

- [x] 2.1 Move `Recognizer`, `recognizerClass`, `speak` and the answer-playing logic from `screens/Ask.tsx` into `pwa/src/voice.ts` (refactor, no behaviour change). Verify: `npx vitest run src/screens/Ask.test.tsx` is green before and after, with no test edited

## 3. Two pages and the Activity page

- [x] 3.1 Write failing tests in `tv.test.ts` for `activityRows`, covering the scenarios "Opening with changes, stills and proof", "At most four stills", "Every opening has its own row", "Still being analyzed", "Older than a week left out" and "Nothing this week". Run them and see them fail because `activityRows` doesn't exist
- [x] 3.2 Implement `activityRows` in `tv.ts`, sharing the proof selection with `recentRows`. Verify: the `tv.test.ts` tests are green and the existing `recentRows` tests are unchanged and green
- [x] 3.3 Write failing component tests for "Opens on the overview", "Right shows Activity", "Left goes back", "Keys at the ends do nothing", "No extra requests when paging", Activity "Events fail", "Broken Activity still hidden", and "No clips or video", "Only opening pictures and the icon shown" and "Back is left to the TV app" on both pages. Run them and see them fail
- [x] 3.4 Implement the page state, the `window` keydown listener, the page indicator and the Activity panel, using `Photo` for its pictures. Verify: `npm test` in `pwa/` is green

## 4. Ask by voice

- [x] 4.1 Write failing component tests with a fake `window.SpeechRecognition` and a fake `api.ask`. Cover "No speech recognition", "Mic has focus", "Listening shown", "Spoken question answered" (with `HTMLMediaElement.prototype.play` stubbed), "No audio in the answer" (with `speechSynthesis` stubbed), "Stopped while listening", "Nothing heard", "Ask fails", "Banner goes away" (fake timers), "Answer on the Activity page", plus "Only the mic button" and "Only the listed endpoints". Run them and see them fail
- [x] 4.2 Implement `useVoiceQuestion` and the mic button and answer banner in the header, using `voice.ts`. Verify: `npm test` in `pwa/` is green
- [x] 4.3 Check the layout in the browser preview at 1920×1080 with the mock API: the overview and Activity pages, the banner, and the mic focus ring. Attach a screenshot to the task report

## 5. Fire TV launcher icon

- [x] 5.1 Write a failing Jest test in `firetv/test/` for "Manifest declares the icon" and "Same icon as the PWA". Run `npm test` in `firetv/` and see it fail
- [x] 5.2 Copy `pwa/public/icon-512.png` into the `firetv/` package and declare it in `manifest.toml` `[package]`. Find the key and path form the Vega validator accepts by running `npm run build:release`, and log friction if the docs or validator are unclear. Verify: `npm test` in `firetv/` is green and the build output has no "Icon is not defined in the manifest" ("Build has no icon warning")

## 6. Deploy and on-device check

- [ ] 6.1 Run every suite and the linters green: `uv run pytest` in `backend/` and `clipblur/`; `npm test` in `pwa/`, `firetv/` and `infra/`; `npm run lint` in `pwa/` and `firetv/`. Report each command and its result
- [ ] 6.2 After Jayson OKs the PWA deploy, rebuild and sideload the Fire TV app on the Vega Virtual Device and check:
  - the launcher icon;
  - the title icon;
  - Right/Left paging with the remote;
  - the Activity page;
  - whether the mic button shows;
  - if it shows, a spoken question with its answer audio.
  
  For each failure (keys not reaching the page, no speech recognition, a microphone prompt, no audio), add a friction-log entry. Then apply design decisions 3 and 9 or record them as follow-ups
