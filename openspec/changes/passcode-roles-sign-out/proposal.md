# Proposal

## Why

The app has one full-access passcode (the owner) and an optional read-only demo passcode. Jayson wants a second full-access passcode for everyday use that does not open the Debug screens, since debug traces hold unblurred stills. The passcode he keeps for himself stays the admin passcode and opens Debug. The app also has no way to sign out: the only way back to the passcode screen is to wait 24 hours or clear site data.

Tracks: AWS Builder (Secrets Manager, API Gateway, Lambda), Open Source.

## What Changes

- **New role `user`.** A third, optional passcode `user_passcode` in the `fridgesense/ring-app` secret signs in with role `user`. A `user` token may do everything an `owner` token may, except the owner-only routes (`GET /api/debug/motions`, `GET /api/debug/motions/{id}`), which answer 403 `{"error": "admin only"}`.
- The existing `passcode` keeps role `owner` (the admin). The demo passcode keeps role `viewer` (read-only).
- Like the others, changing `user_passcode` signs out only the `user` tokens. If two passcodes are equal, the higher role wins (owner, then user, then viewer).
- **PWA:** a `user` gets the full app (editing, Add item, Review actions, all Config edit controls) but no "Debug" Config tab and no "Debug" links on Activity.
- **PWA:** a "Sign out" button in the header, for every role. It removes the stored session and shows the passcode screen. No API call: tokens are stateless and expire on their own.
- The passcode values live only in Secrets Manager. Tests use made-up passcodes.

## Out of scope

- Revoking a single token server-side (sign out is device-local).
- More than one passcode per role, per-person accounts, Cognito.
- Any change to the MCP endpoint, which uses its own `mcp_key`.

## Capabilities

### Modified Capabilities

- `inventory-api`: sign-in accepts a `user` passcode; `user` tokens are refused on owner-only routes.
- `inventory-app`: sign out; Debug hidden for the `user` role.

## Impact

- `backend/src/fridgesense/store.py` (`AppConfig.user_passcode`), `session.py`, `handlers/api.py`
- `pwa/src/api/types.ts`, `session.ts`, `App.tsx`, `AppContext.tsx`, every screen that checks `role === "owner"`
- `pwa/scripts/mock-api.ts` (`FRIDGESENSE_MOCK=user`), README
