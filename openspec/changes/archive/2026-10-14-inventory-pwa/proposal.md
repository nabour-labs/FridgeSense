# Proposal

## Why

The pipeline now writes an inventory, door events and pending changes, but nobody can see them. The demo video needs a phone app that shows the inventory updating after a door opening, the stills Nova looked at, open/close stats, and a quick way to confirm what Nova was unsure about. "Design" is one of the four judging criteria, so the app has to look and feel finished, not like a debug page.

Tracks: **Ring** (the main front end of the Ring-triggered product) and **AWS Builder** (CloudFront + S3 hosting, API on the existing HTTP API).

## What Changes

- **A JSON API under `/api`** on the existing HTTP API, served by a new API Lambda:
  - a passcode sign-in that returns a signed session token
  - a second, **read-only demo passcode** for judges: it signs in to the same data but can't confirm, reject or edit
  - inventory, door events (with short-lived links to their stills), and pending changes
  - confirm or reject a pending change, and set an item's quantity by hand
- **Inventory rules for confirm, reject and manual fixes**, sharing the save step's name normalization and quantity floor.
- **A PWA (`pwa/`)** built with Vite, React, TypeScript, Tailwind, Recharts and vite-plugin-pwa:
  - **Sign in:** the passcode. With the demo passcode, the app shows a "Demo · read-only" badge and hides every edit control.
  - **Fridge:** items by category with quantities, a banner for items to confirm, and an "out of" section.
  - **Activity:** door openings newest first, with time, duration, changes and still thumbnails.
  - **Review:** confirm, edit or reject pending changes.
  - **Stats:** opens per day for the last 7 days, opens by hour of day, today's count and the average time the door stays open.
  - Refreshes every 10 s while visible, so a door opening shows up without reloading. Installable on the phone's home screen.
- **Hosting:** S3 + CloudFront, with `/api/*` routed through the same CloudFront distribution so the app and API share one origin (no CORS). The site URL is a stack output.

## Capabilities

### New Capabilities

- `inventory-api`: authenticated HTTP access to the inventory, door events, pending changes and corrections for the signed-in user.
- `inventory-app`: the installable phone app: sign-in, fridge view, activity with stills, review of pending changes, and stats.

### Modified Capabilities

- `fridge-inventory`: adds three requirements:
  - confirming a pending change applies it to the inventory
  - rejecting one discards it
  - an item's quantity can be set by hand

  The existing requirements are unchanged.

## Out of scope

- Voice, Alexa+ and MCP (`fridge-mcp`).
- Push notifications, multiple users and accounts (the demo viewer is read-only access to the same account, not a second user), and passcode changes from the app.
- Reference photos, item photos, expiry dates and recipes.
- Offline editing. The installed app shell opens offline; data needs the network.
- A custom domain (the CloudFront domain is enough for the demo).

## Impact

- **New code:**
  - `backend/src/fridgesense/api.py`, plus helpers shared with `inventory.py`
  - `pwa/` (new Node package with `npm test` = `vitest run`)
  - an infra construct for the site and the API Lambda
- **AWS:** one Lambda, an S3 bucket, a CloudFront distribution with an origin access control, and one catch-all `/api/{proxy+}` route on the existing HTTP API. Idle cost is cents per month; CloudFront's free tier covers the demo.
- **Deploy:** `cdk deploy` now builds the PWA (`npm run build` in `pwa/`) during bundling, like the Lambda bundling.
- **CI:** picks up `pwa/package.json` automatically.
