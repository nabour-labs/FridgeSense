# Proposal

## Why

Setup warnings ("The camera has moved or changed angle", "Open/close detection is not set up", …) ask for fixes that only the owner makes: retaking door references, saving the fridge area, running setup. Jayson asked on 2026-10-22 for the banners to show to the owner only, so household users and judges signed in with the user or demo passcode don't see maintenance alerts they can't act on.

## What Changes

- **Owner-only banners.** The PWA shows the setup-warning banners on the Fridge and Config screens only when the session's role is `owner`. For `user` and `viewer` sessions the banner area is empty and `GET /api/warnings` is not called.
- **API unchanged.** `GET /api/warnings` still accepts every role; only the app hides the banners.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `setup-warnings`: add "Banners shown to the owner only"; modify "Monitoring paused warning" so its banner scenario no longer describes what a viewer sees.

## Hackathon tracks

None directly; a cleaner app for the demo.
