# Design

## Context

The route table in `handlers/api.py` already supports `owner=True`: a viewer gets 403 `read-only`, and any other non-owner gets 403 `admin only` (as `PUT /api/settings/face-blur` does). Both live routes are `write=True` today. In the PWA, `isAdmin(role)` means owner. `Activity.tsx` and `Camera.tsx` gate the Livestream button and the Decoder card with `canEdit(role)`. `App.tsx` builds `screenApi` with `withSnapshot(api, (signal) => liveSnapshot(api, { signal }))` for every role.

## Decisions

1. **Server first.** Switch both live routes to `owner=True`, so a user can't reach Ring's live video by calling the API directly. Hiding the buttons alone wouldn't be enough.
2. **Gate the UI with `isAdmin(role)`.** Use it for the Livestream button and the Decoder card.
3. **Users' snapshots use `api.cameraSnapshot()` directly.** In `App.tsx`, the snapshot source becomes `liveSnapshot` for the owner and `api.cameraSnapshot()` for everyone else. The Mock video branch stays unchanged. That route already blurs faces on the server and is open to users (`write=True`). The trade-off is that a user's snapshot is the newest recording rather than "now". This keeps reference and door-zone setup working for users without a live session.
4. The `livestream-online-check` "online check before a snapshot" stays in `liveSnapshot`, so it applies to the owner only. A user's snapshot still gets the server's 409/502 messages.

## Risks / Trade-offs

- [A user's setup snapshot may be minutes old] → The 409 message already tells them to walk past the camera. The owner still gets a live frame.
- [An open user session holding a live `session_id` when this deploys] → Its DELETE now gets 403. Ring ends the session on its own after 60 s.

## Test strategy

- **Backend (pytest, contract level):** in `tests/test_api_live.py`, one test per scenario of "Open a live view" and "Close a live view". The fake Ring client asserts it wasn't called for user and viewer tokens. Ring is stubbed as today, with no live calls.
- **PWA (Vitest, component level):**
  - `Activity.test.tsx`: "Button for every role" across the three roles.
  - `Camera.test.tsx`: the Decoder card for owner, user and viewer.
  - An `App` or `screenApi` test for "Users' snapshots from the newest recording", using `fakeApi` with the user role and asserting that `startLive`/`cameraFrame` are never called.
  - The existing `liveSnapshot.test.ts` still covers the owner path.
- No fixtures needed beyond the existing fakes.
