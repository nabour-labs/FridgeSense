# Design

## Context

The pipeline (archived `door-event-pipeline`) writes these items to the single table under `ACCOUNT#<account_id>`:
- `ITEM#<key>`
- `DOOR#<opened_at>#<device>`, with `changes`, `pending_count`, `still_keys`, `status`
- `PENDING#<opened_at>#<n>`

Stills live in the private stills bucket for 7 days. The HTTP API currently has only `/ring/*` routes on the HTTP Lambda. The passcode lives in `fridgesense/ring-app`. One user, one account (`TokenStore().load().account_id`). See proposal.md for scope.

## Goals / Non-Goals

**Goals:**
- One `cdk deploy` builds and ships the PWA and API; the site URL is an output.
- The demo flow (door opens → the Fridge screen updates within the 10 s poll after the pipeline saves) works on a phone.
- The app looks finished: consistent spacing and type, light and dark mode, touch targets of at least 44 px, no layout jumps while polling.

**Non-Goals:**
- Real-time push (WebSockets, AppSync). Polling every 10 s is enough for one viewer.
- Server-side stats: the app computes them from `GET /api/events?days=7`.

## Decisions

### API: a separate Lambda behind one catch-all route
- `ANY /api/{proxy+}` → `fridgesense.handlers.api.handler`, with 256 MB and a 10 s timeout.
- A small dispatch table maps `(method, path pattern)` to functions, using the existing `web.Request` and `json_response` helpers.
- *Alternative:* add routes to the HTTP Lambda. That would mix the Ring webhook's 200-always rules with the app's auth rules, and give one role every permission.

### Session tokens without a new secret
- **Format:** `<base64url(json {"exp": <epoch s>})>.<hex HMAC_SHA256(key, payload)>`.
- **Key:** `HMAC_SHA256(passcode, "fridgesense-session-v1")`, so changing the passcode invalidates every token.
- **Checks:** constant-time comparison, and the expiry is checked after the signature.
- **Lifetime:** 30 days.
- **Client storage:** `localStorage` under `fridgesense.token`; acceptable for a single-user demo app on the owner's phone.
- *Alternative:* Cognito. It was cut from the MVP scope, and it adds a hosted UI and token refresh.

### IDs in URLs
- **Door event and pending IDs:** `base64url(sk)`, which is opaque. It round-trips without `#` or `:` in paths, and anything that doesn't decode to the expected prefix is a 404.
- **Item keys:** the normalized name, URL-encoded (`/api/items/whole%20milk`).

### Shared inventory logic
- `inventory.py` gains:
  - `quantity_put(current, key, display, category, delta, when)`, which builds the item write (floor at 0; no item when removing an unknown one)
  - `set_quantity(...)`
- `save_task` uses the same `quantity_put`.
- `save_task` also stores `change_index` (the position in the door event's `changes`) on each pending item. Confirm and reject then update `changes[<i>].applied` or `.rejected` and `pending_count - 1` in the same transaction that deletes the pending item. The condition is that the pending item still exists, so a double tap can't apply it twice.

### Stills in the app
- `GET /api/events` returns S3 presigned GET URLs (`ExpiresIn=900`) for events opened in the last 7 days, matching the bucket's lifecycle.
- *Alternative:* serve stills through CloudFront. That needs signed cookies or URLs and a second origin; presigning is one call.

### Events query
- `FridgeTable.query_range(account_id, "DOOR#<since ISO>", "DOOR#~")` uses `sk BETWEEN`, with `ScanIndexForward=False` for newest first.
- `days` is validated as an integer from 1 to 30.

### Hosting: CloudFront in front of both the site and the API
- **Site:** a private bucket `fridgesense-site-<account>` and a CloudFront distribution with an origin access control.
  - `defaultRootObject: index.html`.
  - 403 and 404 → `/index.html` with 200, so a reload on any screen works.
- **API:** the `/api/*` behavior points at the HTTP API's domain.
  - Cache policy `CACHING_DISABLED`, origin request policy `ALL_VIEWER_EXCEPT_HOST_HEADER` (passes `Authorization` and the query string), all methods allowed.
  - The app calls relative `/api/...` URLs, so there's no CORS and no API URL in the build.
- **Deploy:** `BucketDeployment` from `Source.asset("../pwa")` with local bundling (`npm ci && npm run build`, then copy `dist/`), with a distribution invalidation of `/*`. Tests disable bundling like the Lambda assets.
- Output: `SiteUrl`.

### PWA stack and structure
- **Stack:**
  - Vite 8, React 19, TypeScript, Tailwind CSS v4 (`@tailwindcss/vite`)
  - Recharts, `lucide-react` icons
  - `vite-plugin-pwa` (`generateSW`)
- **Screens:** four tabs in a bottom bar (Fridge, Activity, Review, Stats), switched by `location.hash` with no router dependency. Sign-in replaces the tabs when there is no token.
- **Data layer:**
  - A typed `ApiClient` (fetch wrapper that adds the bearer token and throws `Unauthorized` on 401 and `Offline` on a network error), provided by React context so tests inject a fake.
  - `usePolling(fn, 10_000)` runs on mount and on `visibilitychange` back to visible, and pauses while hidden.
- **Stats:** pure functions in `stats.ts` (`perDay`, `perHour`, `todayCount`, `averageDuration`) using `Intl.DateTimeFormat().resolvedOptions().timeZone`, with an injectable time zone for tests.
- **PWA config:**
  - The manifest lives in `src/manifest.ts`, imported by `vite.config.ts` so it can be unit-tested.
  - The workbox config sets `navigateFallback: "index.html"` and `navigateFallbackDenylist: [/^\/api\//]`, and never caches `/api`.
  - Icons: `public/icon-192.png` and `public/icon-512.png`, generated once from an SVG and committed.
- **Visual design:**
  - Calm "cool fridge" palette: slate neutrals, an ice-blue accent, green for added, amber for "to confirm", rose for removed.
  - Large numerals for quantities; `prefers-color-scheme` dark mode; safe-area padding for notched phones.
  - Skeletons on first load only, not on every poll.

## Test strategy

| Level | What | How |
| --- | --- | --- |
| Unit (pytest) | Token sign and verify (expiry, tampering, passcode change), ID encoding, `quantity_put`, query parameter validation | Pure functions with a fixed clock |
| Integration (pytest + moto) | Every `inventory-api` scenario through `api.handler` with API Gateway v2 events; confirm, reject and set-quantity rules against moto DynamoDB; presigned URLs against moto S3 (URL has the key, `X-Amz-Expires=900` and a signature) | `aws` fixture plus seeded items, door events and pending items |
| Regression (pytest) | Existing save-task tests still pass, now with `change_index` stored on pending items | Existing suite |
| Unit (Vitest) | `stats.ts` (per day and per hour in a given time zone, averages, empty input), `ApiClient` (bearer header, 401 → `Unauthorized`, network error → `Offline`), manifest and workbox config | jsdom, `vi.fn` fetch |
| Component (Vitest + Testing Library) | Each `inventory-app` scenario: sign-in, Fridge grouping, out-of section, pending banner, empty state, polling with fake timers and `document.visibilityState`, quantity edit; Activity rendering and stills dialog; Review confirm, edit and reject; Stats numbers | Fake `ApiClient` through context; `vi.useFakeTimers()` |
| Infra (Vitest) | API Lambda and the `/api/{proxy+}` route; site bucket private; distribution with OAC, SPA error responses and an `/api/*` behavior with caching disabled and all methods; `SiteUrl` output; API Lambda grants (table read and write, app and token secret read, stills bucket read only) | `Template.fromStack` with bundling disabled |

No test calls Ring, AWS or Bedrock. The PWA tests never hit the network.

## Risks / Trade-offs

- [The token is in localStorage, readable by any script on the origin] → The app ships no third-party scripts, and CloudFront serves only our own files. Acceptable for a single-user demo; noted in the README.
- [Presigned URLs leak if a screenshot is shared] → They expire in 15 minutes and the bucket deletes stills after 7 days.
- [Polling costs] → One user, one request every 10 s while the app is open: well within the free tier.
- [Vite 8 or Tailwind 4 API changes] → Pin exact versions in `package-lock.json`; the tests cover the build config.
- [CloudFront deploys are slow (5–10 min)] → Deploy once on Oct 19, then iterate on the PWA locally with `npm run dev` and a dev proxy to the deployed `/api`.

## Migration Plan

1. `cdk deploy` (with Jayson's approval) adds the site bucket, the distribution, the API Lambda and the route.
2. Existing pending items written before this change have no `change_index`. Confirm and reject then skip the door-event update and only apply or delete; there is no production data yet, so this is a fallback only.
3. Rollback: redeploy the previous commit; the data is untouched.
