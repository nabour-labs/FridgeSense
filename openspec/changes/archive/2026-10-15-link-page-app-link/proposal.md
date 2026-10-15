## Why

After linking, the "Camera linked" page is a dead end: the user has to find the app's CloudFront URL on their own. A link to the app finishes the setup flow in one tap.

Tracks: **Ring** (account linking flow into the main front end).

## What Changes

- The "Camera linked" page shows an "Open FridgeSense" link to the app's site URL.
- The HTTP Lambda gets the site URL as `APP_URL` from the CDK stack.
- With no `APP_URL` set, the page renders as before, without the link.

## Out of scope

- Signing the user into the app automatically (the app keeps its own passcode sign-in).
- Links on the error pages.
- A custom domain.

## Impact

- `backend/src/fridgesense/link_page.py`, `linking.py`, `handlers/http.py`
- `infra/lib/fridgesense-stack.ts` (one env var on `HttpFunction`)
- No new AWS resources, no cost.
