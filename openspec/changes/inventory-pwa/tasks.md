# Tasks

## 1. Inventory rules for confirm, reject and manual fixes

- [x] 1.1 Write failing tests that `save_task` stores `change_index` on pending items (extending "Low-confidence item") and that `quantity_put` keeps the floor-at-0 and no-unknown-removal rules; verify they fail
- [x] 1.2 Extract `quantity_put` from `save_task`, store `change_index`, and keep the whole existing suite green
- [x] 1.3 Write failing moto tests for "Confirm as reported", "Confirm with a correction", "Confirm a removal of an unknown item" and "Reject" (inventory, pending item and door event `changes[i]` plus `pending_count`); verify they fail
- [x] 1.4 Implement `confirm_pending` and `reject_pending` as conditional transactions (pending must still exist) to make the tests pass
- [x] 1.5 Write failing tests for "Correct a count" and "Add an item by hand"; then implement `set_quantity` and verify they pass

## 2. API: sessions and routing

- [x] 2.1 Write failing unit tests for token signing and verification: valid, expired, tampered, signed with an old passcode, viewer role, viewer token after the demo passcode changes, and viewer token with no demo passcode configured; verify they fail
- [x] 2.2 Implement `session.py` (issue and verify with a `role` claim, key derived from that role's passcode) to make the tests pass
- [x] 2.3 Write failing handler tests for "Correct passcode", "Wrong passcode", "Passcode changed", "Demo passcode", "No demo passcode configured", "Demo passcode changed", "No token", "Tampered or expired token", "Unknown route" and "No linked Ring account"; verify they fail
- [x] 2.4 Implement `handlers/api.py` with the dispatch table, `POST /api/session` and auth gating to make the tests pass

## 3. API: reads

- [x] 3.1 Write failing tests for "Inventory with items" and "Empty inventory"; then implement `GET /api/inventory` and verify they pass
- [x] 3.2 Write failing tests (moto S3 + DynamoDB) for "Recent event with stills", "Old event", "Range limit" and "Days out of range"; verify they fail
- [x] 3.3 Implement `FridgeTable.query_range`, opaque IDs and `GET /api/events` with presigned still links to make the tests pass

## 4. API: writes

- [x] 4.1 Write failing tests for `GET /api/pending`, "Confirm over HTTP", "Pending change not found" and "Invalid quantity" (confirm and `PUT /api/items/{key}`), plus reject over HTTP, "Viewer write refused" and "Viewer reads"; verify they fail
- [x] 4.2 Implement the pending, confirm, reject and set-quantity routes on top of the inventory functions, with write routes refusing viewer tokens, to make the tests pass

## 5. PWA scaffold and data layer

- [x] 5.1 Create `pwa/` (Vite 8, React 19, TypeScript, Tailwind v4, Recharts, lucide-react, vite-plugin-pwa, Vitest + Testing Library + jsdom; `npm test` = `vitest run`); verify `npm test` runs and `npm run build` produces `dist/index.html`
- [x] 5.2 Write failing tests for `ApiClient`: bearer header, JSON bodies, 401 → `Unauthorized`, 403 → `ReadOnly`, network failure → `Offline`; then implement it and verify the tests pass
- [x] 5.3 Write failing tests for `usePolling` (fake timers): immediate call, repeat every 10 s, no calls while `document.visibilityState` is hidden, a call on becoming visible; then implement it and verify the tests pass

## 6. PWA screens

- [x] 6.1 Write failing component tests for "First visit", "Successful sign-in", "Wrong passcode" and "Session expired"; then implement the sign-in screen, token storage and app shell, and verify they pass
- [x] 6.2 Write failing component tests for "Items by category", "Out of stock", "Pending banner", "Empty fridge", "Live refresh", "Hidden app does not poll" and "Fix a quantity"; verify they fail
- [x] 6.3 Implement the Fridge screen (grouping, out-of section, banner, quantity editor) to make the tests pass
- [x] 6.4 Write failing component tests for "Door opening shown", "Stills" and "Failed analysis"; then implement the Activity screen and stills dialog, and verify they pass
- [x] 6.5 Write failing component tests for "Confirm", "Edit and confirm", "Reject" and "Nothing to review"; then implement the Review screen and verify they pass
- [x] 6.6 Write failing unit tests for `stats.ts` covering "Stats from events", "Local time zone" and "No openings yet"; verify they fail
- [x] 6.7 Implement `stats.ts` and the Stats screen (Recharts bars, today, average) to make the tests pass, including a component test that renders the numbers for "Stats from events"
- [ ] 6.8 Write failing tests for "Manifest" (from `src/manifest.ts`) and "Offline shell" (workbox `navigateFallback` and `/api` denylist; the app shows the can't-reach message when `ApiClient` throws `Offline`); then add the manifest, icons and PWA config, and verify they pass
- [ ] 6.9 Write failing component tests for "Demo sign-in", "No edits on Fridge", "No actions on Review" and "Write refused"; then store the role, add the badge and gate the edit controls, and verify they pass
- [ ] 6.10 Polish pass: dark mode, 360 px layout with no horizontal scroll, 44 px touch targets, no layout jumps while polling. Verify with `npm run build && npm run preview` in the browser at 360×740 and at desktop width, light and dark

## 7. Infrastructure

- [ ] 7.1 Write failing Vitest assertions for the API Lambda (`fridgesense.handlers.api.handler`, arm64, 256 MB, 10 s), the `ANY /api/{proxy+}` route, and its grants (table read and write, app and token secret read, stills bucket read only, no Bedrock or Step Functions); verify they fail
- [ ] 7.2 Write failing Vitest assertions for the site: private bucket, distribution with OAC and `index.html` default, 403/404 → `/index.html` 200, an `/api/*` behavior to the HTTP API with caching disabled, all methods and `ALL_VIEWER_EXCEPT_HOST_HEADER`, and a `SiteUrl` output; verify they fail
- [ ] 7.3 Implement the API Lambda and the site construct (`BucketDeployment` with local `npm ci && npm run build` bundling) to make the tests pass; verify `cdk synth` with real bundling includes `index.html` and `manifest.webmanifest` in the site asset

## 8. Docs and final check

- [ ] 8.1 Update the README: opening the app (the `SiteUrl` output), the passcode command, installing to the home screen, local PWA development (`npm run dev` with a proxy to the deployed API), the localStorage token note, and a "Try it (judges)" section with the `SiteUrl`, the demo passcode, what a viewer can see, the command that sets `demo_passcode` in `fridgesense/ring-app`, and a reminder to remove it after judging; verify the commands match the code
- [ ] 8.2 Run `cd backend && uv run pytest && uv run ruff check && uv run ruff format --check`, `cd pwa && npm test && npx tsc --noEmit && npm run build`, and `cd infra && npm test && npx tsc --noEmit`; all green
