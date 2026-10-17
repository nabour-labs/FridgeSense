# Design

## Roles

| Passcode field | Role | Reads | Writes | Debug |
|---|---|---|---|---|
| `passcode` | `owner` (admin) | yes | yes | yes |
| `user_passcode` | `user` | yes | yes | no |
| `demo_passcode` | `viewer` | yes | no | no |

`session._passcode_for` gains `"user": cfg.user_passcode`, and `sign_in` tries `owner`, `user`, `viewer` in that order. Each role's signing key is still derived from its own passcode, so changing one passcode invalidates only that role's tokens, and an unset passcode means the role cannot sign in or verify.

The route table keeps its two flags. The check becomes, in order:

- role is `viewer` and the route is `write` or `owner`: 403 `{"error": "read-only"}` (unchanged);
- role is `user` and the route is `owner`: 403 `{"error": "admin only"}`.

Viewers keep their existing error so the debug-traces scenarios stay as written.

## PWA

`AppContext` exposes two helpers so screens stop comparing role strings:

- `canEdit(role)`: role is not `viewer`;
- `isAdmin(role)`: role is `owner`.

Screens that used `role === "owner"` for edit controls switch to `canEdit`. Config's Debug tab and Activity's Debug link switch to `isAdmin`. `loadSession` keeps any of the three stored roles and falls back to `owner` only for sessions from before roles were stored, as today.

**Sign out:** a 44 px icon button (`LogOut`, `aria-label="Sign out"`) in the header next to the Config gear. Tapping calls `clearSession()` and clears the in-memory session; the app renders the sign-in screen. There is no confirmation: signing back in takes one passcode.

## Secrets

The two passcodes are written to `fridgesense/ring-app` with `put-secret-value`, built from the current secret with `jq --arg`, values read from a hidden prompt or file in the scratchpad, never committed. The Lambdas cache the secret for up to 5 minutes.

## Test strategy

- **Unit (pytest, moto Secrets Manager):** `test_session.py` and `test_api_auth.py` cover user sign-in, the role order, user passcode change, user writes and user 403 on debug routes. Passcodes are made-up fixture values.
- **Component (Vitest + Testing Library):** sign-out from the header, `user` role sees edit controls but no Debug tab or link, `user` role is restored from storage.
- **Manual:** mock API with `FRIDGESENSE_MOCK=user` in the browser preview.
